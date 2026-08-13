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

def migrate_specific_user(cur, conn, old_user_id: str, new_user_id: str) -> None:
    '''Move one anonymous user_id account (settings + receipts + telegram links) into canonical ecom_{login} id'''
    if not old_user_id or old_user_id == new_user_id:
        return

    cur.execute("UPDATE receipts SET user_id = %s WHERE user_id = %s", (new_user_id, old_user_id))

    cur.execute("SELECT 1 FROM user_settings WHERE user_id = %s", (new_user_id,))
    if cur.fetchone():
        cur.execute(
            "UPDATE user_settings AS c SET "
            "group_code = COALESCE(NULLIF(c.group_code, ''), o.group_code), "
            "inn = COALESCE(NULLIF(c.inn, ''), o.inn), "
            "sno = COALESCE(NULLIF(c.sno, ''), o.sno), "
            "default_vat = COALESCE(NULLIF(c.default_vat, ''), o.default_vat), "
            "company_email = COALESCE(NULLIF(c.company_email, ''), o.company_email), "
            "payment_address = COALESCE(NULLIF(c.payment_address, ''), o.payment_address), "
            "active_ai_provider = COALESCE(NULLIF(c.active_ai_provider, ''), o.active_ai_provider), "
            "gigachat_auth_key = COALESCE(NULLIF(c.gigachat_auth_key, ''), o.gigachat_auth_key), "
            "yandexgpt_api_key = COALESCE(NULLIF(c.yandexgpt_api_key, ''), o.yandexgpt_api_key), "
            "yandexgpt_folder_id = COALESCE(NULLIF(c.yandexgpt_folder_id, ''), o.yandexgpt_folder_id), "
            "gptunnel_api_key = COALESCE(NULLIF(c.gptunnel_api_key, ''), o.gptunnel_api_key) "
            "FROM user_settings AS o "
            "WHERE c.user_id = %s AND o.user_id = %s",
            (new_user_id, old_user_id)
        )
        cur.execute("DELETE FROM user_settings WHERE user_id = %s", (old_user_id,))
    else:
        cur.execute("UPDATE user_settings SET user_id = %s WHERE user_id = %s", (new_user_id, old_user_id))

    cur.execute("UPDATE telegram_links SET user_id = %s WHERE user_id = %s", (new_user_id, old_user_id))
    conn.commit()


def merge_orphan_accounts(cur, conn, canonical_user_id: str, login: str) -> None:
    '''Find any other user_id rows tied to the same Ecomkassa login (e.g. from another device) and merge them in'''
    cur.execute(
        "SELECT user_id FROM user_settings WHERE ecomkassa_login = %s AND user_id != %s",
        (login, canonical_user_id)
    )
    orphan_ids = [row[0] for row in cur.fetchall()]
    for orphan_id in orphan_ids:
        migrate_specific_user(cur, conn, orphan_id, canonical_user_id)


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
        
        # Auto-merge: if this account has an Ecomkassa login, silently pull in any other
        # accounts (from other browsers/devices/Telegram) tied to the same login
        login = settings.get('ecomkassa_login', '')
        if login:
            cur = conn.cursor()
            merge_orphan_accounts(cur, conn, user_id, login)
            cur.close()
        
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