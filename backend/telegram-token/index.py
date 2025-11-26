import json
import os
import psycopg2
import hashlib
import time
from typing import Dict, Any

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Сохранение и получение токена Telegram бота
    Args: event - dict с httpMethod, headers с X-Admin-Token, body с token
          context - объект с request_id
    Returns: HTTP response с токеном или статусом сохранения
    '''
    method: str = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Token',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }
    
    headers = event.get('headers', {})
    admin_token = headers.get('X-Admin-Token') or headers.get('x-admin-token')
    
    print(f"DEBUG: Received token: {admin_token[:20] if admin_token else 'None'}...")
    
    if not admin_token:
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'No token provided'})
        }
    
    admin_password = os.environ.get('ADMIN_PASSWORD', '')
    if not admin_password:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Admin not configured'})
        }
    
    current_time = int(time.time())
    valid_tokens = []
    for offset in range(-3600, 3601, 60):
        token_data = f"{admin_password}:{current_time + offset}"
        valid_tokens.append(hashlib.sha256(token_data.encode()).hexdigest())
    
    print(f"DEBUG: Generated {len(valid_tokens)} valid tokens")
    print(f"DEBUG: Sample expected token: {valid_tokens[0][:20]}...")
    print(f"DEBUG: Token match: {admin_token in valid_tokens}")
    
    if admin_token not in valid_tokens:
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Invalid or expired token'})
        }
    
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Database not configured'})
        }
    
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    
    try:
        if method == 'GET':
            cur.execute(
                "SELECT setting_value FROM ai_settings WHERE setting_key = 'telegram_bot_token'"
            )
            result = cur.fetchone()
            
            token = result[0] if result else '8367558133:AAG8btCuHLitqaRlgS_HwUsgSIRO8bZJCr0'
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'isBase64Encoded': False,
                'body': json.dumps({'token': token})
            }
        
        elif method == 'POST':
            body_data = json.loads(event.get('body', '{}'))
            token = body_data.get('token', '')
            
            if not token:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': 'Token required'})
                }
            
            cur.execute(
                """
                INSERT INTO ai_settings (setting_key, setting_value)
                VALUES ('telegram_bot_token', %s)
                ON CONFLICT (setting_key) 
                DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = CURRENT_TIMESTAMP
                """,
                (token,)
            )
            conn.commit()
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'isBase64Encoded': False,
                'body': json.dumps({'success': True})
            }
        
        else:
            return {
                'statusCode': 405,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Method not allowed'})
            }
            
    finally:
        cur.close()
        conn.close()