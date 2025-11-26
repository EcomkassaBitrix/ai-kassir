import json
import os
import psycopg2
from typing import Dict, Any

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Admin API for managing AI provider settings for all users
    Args: event with httpMethod, body, headers; context with request_id
    Returns: HTTP response with users list or update confirmation
    '''
    method: str = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Password',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }
    
    admin_password = event.get('headers', {}).get('x-admin-password') or event.get('headers', {}).get('X-Admin-Password')
    correct_password = os.environ.get('ADMIN_PASSWORD', '')
    
    if not admin_password or admin_password != correct_password:
        return {
            'statusCode': 401,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Unauthorized'})
        }
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Database not configured'})
        }
    
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    
    if method == 'GET':
        cur.execute('''
            SELECT user_id, active_ai_provider, gigachat_auth_key, 
                   yandexgpt_api_key, yandexgpt_folder_id, gptunnel_api_key
            FROM user_settings
            ORDER BY user_id
        ''')
        
        rows = cur.fetchall()
        users = []
        for row in rows:
            users.append({
                'user_id': row[0],
                'active_ai_provider': row[1] or '',
                'gigachat_auth_key': row[2] or '',
                'yandexgpt_api_key': row[3] or '',
                'yandexgpt_folder_id': row[4] or '',
                'gptunnel_api_key': row[5] or ''
            })
        
        cur.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'users': users})
        }
    
    if method == 'POST':
        body_data = json.loads(event.get('body', '{}'))
        user_id = body_data.get('user_id')
        active_ai_provider = body_data.get('active_ai_provider', '')
        gigachat_auth_key = body_data.get('gigachat_auth_key', '')
        yandexgpt_api_key = body_data.get('yandexgpt_api_key', '')
        yandexgpt_folder_id = body_data.get('yandexgpt_folder_id', '')
        gptunnel_api_key = body_data.get('gptunnel_api_key', '')
        
        if not user_id:
            cur.close()
            conn.close()
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'user_id required'})
            }
        
        cur.execute('''
            UPDATE user_settings 
            SET active_ai_provider = %s,
                gigachat_auth_key = %s,
                yandexgpt_api_key = %s,
                yandexgpt_folder_id = %s,
                gptunnel_api_key = %s
            WHERE user_id = %s
        ''', (active_ai_provider, gigachat_auth_key, yandexgpt_api_key, 
              yandexgpt_folder_id, gptunnel_api_key, user_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'success': True, 'user_id': user_id})
        }
    
    return {
        'statusCode': 405,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': 'Method not allowed'})
    }
