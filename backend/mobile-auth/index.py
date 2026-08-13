import json
import os
import datetime
import requests
import urllib3
import psycopg2
from typing import Dict, Any

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN_URL = 'https://app.ecomkassa.ru/fiscalorder/v5/getToken'
TOKEN_TTL_HOURS = 24


def migrate_specific_user(cur, conn, old_user_id: str, new_user_id: str) -> None:
    '''Move one anonymous/foreign user_id account (settings + receipts + telegram links) into canonical ecom_{login} id'''
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
    '''Find any other user_id rows tied to the same Ecomkassa login (other browser/device/Telegram) and merge them in'''
    cur.execute(
        "SELECT user_id FROM user_settings WHERE ecomkassa_login = %s AND user_id != %s",
        (login, canonical_user_id)
    )
    orphan_ids = [row[0] for row in cur.fetchall()]
    for orphan_id in orphan_ids:
        migrate_specific_user(cur, conn, orphan_id, canonical_user_id)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Mobile app login via Ecomkassa login/password, returns Ecomkassa token linked to user_id
    Args: event with httpMethod POST, body (login, password)
    Returns: HTTP response with Ecomkassa token and user_id
    '''
    method: str = event.get('httpMethod', 'GET')

    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '86400'
            },
            'body': '',
            'isBase64Encoded': False
        }

    if method != 'POST':
        return {
            'statusCode': 405,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Method not allowed'})
        }

    body_str = event.get('body', '')
    try:
        body_data = json.loads(body_str) if body_str else {}
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Invalid JSON'})
        }

    login = body_data.get('login', '').strip()
    password = body_data.get('password', '')

    if not login or not password:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Login and password required'})
        }

    try:
        token_response = requests.post(
            TOKEN_URL,
            json={'login': login, 'pass': password},
            headers={'Content-Type': 'application/json; charset=utf-8'},
            timeout=10,
            verify=False
        )
    except requests.RequestException as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': f'Request to Ecomkassa failed: {str(e)}'})
        }

    if token_response.status_code != 200:
        return {
            'statusCode': token_response.status_code,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': token_response.text
        }

    token_data = token_response.json()
    if token_data.get('code') != 0:
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': token_data.get('text', 'Неверный логин или пароль')})
        }

    token = token_data.get('token')
    if not token:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'No token in response'})
        }

    user_id = f'ecom_{login}'
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_TTL_HOURS)

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Database not configured'})
        }

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO user_settings (user_id, ecomkassa_login, ecomkassa_password, updated_at) "
        "VALUES (%s, %s, %s, CURRENT_TIMESTAMP) "
        "ON CONFLICT (user_id) DO UPDATE SET "
        "ecomkassa_login = EXCLUDED.ecomkassa_login, "
        "ecomkassa_password = EXCLUDED.ecomkassa_password, "
        "updated_at = CURRENT_TIMESTAMP",
        (user_id, login, password)
    )

    cur.execute(
        "INSERT INTO ecomkassa_sessions (token, user_id, expires_at, updated_at) "
        "VALUES (%s, %s, %s, CURRENT_TIMESTAMP) "
        "ON CONFLICT (token) DO UPDATE SET "
        "user_id = EXCLUDED.user_id, "
        "expires_at = EXCLUDED.expires_at, "
        "updated_at = CURRENT_TIMESTAMP",
        (token, user_id, expires_at)
    )

    # Auto-merge: pull in any other accounts (web/Telegram/other devices) tied to
    # this same Ecomkassa login into the canonical ecom_{login} account
    merge_orphan_accounts(cur, conn, user_id, login)

    conn.commit()
    cur.close()
    conn.close()

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'isBase64Encoded': False,
        'body': json.dumps({'token': token, 'user_id': user_id})
    }