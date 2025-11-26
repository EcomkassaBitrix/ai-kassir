import json
import os
import psycopg2
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
    
    if not admin_token:
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Admin access required'})
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
                "SELECT setting_value FROM bot_settings WHERE setting_key = 'telegram_bot_token'"
            )
            token_result = cur.fetchone()
            
            cur.execute(
                "SELECT setting_value FROM bot_settings WHERE setting_key = 'telegram_notifications_enabled'"
            )
            enabled_result = cur.fetchone()
            
            token = token_result[0] if token_result else ''
            enabled = enabled_result[0] == 'true' if enabled_result else False
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'isBase64Encoded': False,
                'body': json.dumps({'token': token, 'enabled': enabled})
            }
        
        elif method == 'POST':
            body_data = json.loads(event.get('body', '{}'))
            token = body_data.get('token')
            enabled = body_data.get('enabled')
            
            if token is not None:
                if not token:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                        'body': json.dumps({'error': 'Token required'})
                    }
                
                cur.execute(
                    """
                    INSERT INTO bot_settings (setting_key, setting_value)
                    VALUES ('telegram_bot_token', %s)
                    ON CONFLICT (setting_key) 
                    DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = CURRENT_TIMESTAMP
                    """,
                    (token,)
                )
            
            if enabled is not None:
                enabled_str = 'true' if enabled else 'false'
                cur.execute(
                    """
                    INSERT INTO bot_settings (setting_key, setting_value)
                    VALUES ('telegram_notifications_enabled', %s)
                    ON CONFLICT (setting_key) 
                    DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = CURRENT_TIMESTAMP
                    """,
                    (enabled_str,)
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