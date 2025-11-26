import json
import os
import psycopg2
import secrets
from typing import Dict, Any
from datetime import datetime, timedelta

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Генерирует код для привязки Telegram к user_id
    Args: event - dict с httpMethod, headers с X-User-Id
          context - объект с request_id
    Returns: HTTP response с link_code и bot_url
    '''
    method: str = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-User-Id',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }
    
    if method != 'POST':
        return {
            'statusCode': 405,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Method not allowed'})
        }
    
    headers = event.get('headers', {})
    user_id = headers.get('X-User-Id') or headers.get('x-user-id')
    
    if not user_id:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'User ID required'})
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
        link_code = generate_link_code()
        expires_at = datetime.now() + timedelta(hours=24)
        
        cur.execute(
            "INSERT INTO telegram_links (link_code, user_id, expires_at) VALUES (%s, %s, %s)",
            (link_code, user_id, expires_at)
        )
        conn.commit()
        
        bot_url = f"https://t.me/ecomkassa_ai_bot?start={link_code}"
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'isBase64Encoded': False,
            'body': json.dumps({
                'link_code': link_code,
                'bot_url': bot_url,
                'expires_at': expires_at.isoformat()
            })
        }
        
    finally:
        cur.close()
        conn.close()


def generate_link_code() -> str:
    return f"LINK-{secrets.token_urlsafe(8).upper()}"
