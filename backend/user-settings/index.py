import json
import os
import psycopg2
from typing import Dict, Any, Optional

def get_user_settings(user_id: str, conn) -> Optional[Dict[str, Any]]:
    '''Get user settings from database'''
    cur = conn.cursor()
    cur.execute(
        "SELECT group_code, inn, sno, default_vat, company_email, payment_address, ecomkassa_login, ecomkassa_password, "
        "active_ai_provider, gigachat_auth_key, yandexgpt_api_key, yandexgpt_folder_id, gptunnel_api_key "
        "FROM user_settings WHERE user_id = %s",
        (user_id,)
    )
    row = cur.fetchone()
    cur.close()
    
    if row:
        return {
            'group_code': row[0] or '',
            'inn': row[1] or '',
            'sno': row[2] or 'usn_income',
            'default_vat': row[3] or 'none',
            'company_email': row[4] or '',
            'payment_address': row[5] or '',
            'ecomkassa_login': row[6] or '',
            'ecomkassa_password': row[7] or '',
            'active_ai_provider': row[8] or '',
            'gigachat_auth_key': row[9] or '',
            'yandexgpt_api_key': row[10] or '',
            'yandexgpt_folder_id': row[11] or '',
            'gptunnel_api_key': row[12] or ''
        }
    return None

def save_user_settings(user_id: str, settings: Dict[str, Any], conn) -> None:
    '''Save or update user settings in database'''
    cur = conn.cursor()
    
    cur.execute(
        "INSERT INTO user_settings (user_id, group_code, inn, sno, default_vat, company_email, payment_address, ecomkassa_login, ecomkassa_password, "
        "active_ai_provider, gigachat_auth_key, yandexgpt_api_key, yandexgpt_folder_id, gptunnel_api_key, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP) "
        "ON CONFLICT (user_id) DO UPDATE SET "
        "group_code = EXCLUDED.group_code, "
        "inn = EXCLUDED.inn, "
        "sno = EXCLUDED.sno, "
        "default_vat = EXCLUDED.default_vat, "
        "company_email = EXCLUDED.company_email, "
        "payment_address = EXCLUDED.payment_address, "
        "ecomkassa_login = EXCLUDED.ecomkassa_login, "
        "ecomkassa_password = EXCLUDED.ecomkassa_password, "
        "active_ai_provider = EXCLUDED.active_ai_provider, "
        "gigachat_auth_key = EXCLUDED.gigachat_auth_key, "
        "yandexgpt_api_key = EXCLUDED.yandexgpt_api_key, "
        "yandexgpt_folder_id = EXCLUDED.yandexgpt_folder_id, "
        "gptunnel_api_key = EXCLUDED.gptunnel_api_key, "
        "updated_at = CURRENT_TIMESTAMP",
        (
            user_id,
            settings.get('group_code', ''),
            settings.get('inn', ''),
            settings.get('sno', 'usn_income'),
            settings.get('default_vat', 'none'),
            settings.get('company_email', ''),
            settings.get('payment_address', ''),
            settings.get('ecomkassa_login', ''),
            settings.get('ecomkassa_password', ''),
            settings.get('active_ai_provider', ''),
            settings.get('gigachat_auth_key', ''),
            settings.get('yandexgpt_api_key', ''),
            settings.get('yandexgpt_folder_id', ''),
            settings.get('gptunnel_api_key', '')
        )
    )
    
    conn.commit()
    cur.close()

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Save and load user ecomkassa settings per anonymous user_id
    Args: event with httpMethod (GET/POST), headers with X-User-Id, body with settings
    Returns: User settings from database
    '''
    method: str = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-User-Id',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }
    
    headers = event.get('headers', {})
    user_id = headers.get('x-user-id') or headers.get('X-User-Id')
    
    if not user_id:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'X-User-Id header required'})
        }
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Database not configured'})
        }
    
    conn = psycopg2.connect(database_url)
    
    if method == 'GET':
        settings = get_user_settings(user_id, conn)
        conn.close()
        
        if settings is None:
            settings = {
                'group_code': '',
                'inn': '',
                'sno': 'usn_income',
                'default_vat': 'none',
                'company_email': '',
                'payment_address': '',
                'ecomkassa_login': '',
                'ecomkassa_password': ''
            }
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'isBase64Encoded': False,
            'body': json.dumps({'settings': settings})
        }
    
    if method == 'POST':
        body_data = json.loads(event.get('body', '{}'))
        settings = body_data.get('settings', {})
        
        save_user_settings(user_id, settings, conn)
        conn.close()
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'isBase64Encoded': False,
            'body': json.dumps({'status': 'saved', 'settings': settings})
        }
    
    conn.close()
    return {
        'statusCode': 405,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({'error': 'Method not allowed'})
    }