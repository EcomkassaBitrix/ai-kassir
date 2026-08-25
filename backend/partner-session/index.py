import json
import os
import re
import secrets
import datetime
import requests
import urllib3
import psycopg2
from typing import Dict, Any, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN_URL = 'https://app.ecomkassa.ru/fiscalorder/v5/getToken'
EMBED_TOKEN_TTL_SECONDS = 60


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


def verify_ecomkassa_credentials(login: str, password: str) -> Optional[str]:
    '''Verify login/password against Ecomkassa and return an API token if valid'''
    try:
        resp = requests.post(
            TOKEN_URL,
            json={'login': login, 'pass': password},
            headers={'Content-Type': 'application/json; charset=utf-8'},
            timeout=10,
            verify=False
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    data = resp.json()
    if data.get('code') != 0:
        return None

    return data.get('token')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Server-to-server endpoint for partner LK backends. Exchanges a partner secret
    plus Ecomkassa login/password for a one-time embed token used to open the AI cashier chat
    in an iframe with settings already loaded (no manual login inside the iframe).
    Args: event with httpMethod POST, header X-Partner-Secret, body (ecomkassa_login, ecomkassa_password)
    Returns: HTTP response with embed_token, embed_path, expires_in, user_id
    '''
    method: str = event.get('httpMethod', 'GET')

    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-Partner-Secret',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }

    if method != 'POST':
        return {
            'statusCode': 405,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Method not allowed'})
        }

    headers = event.get('headers', {})
    partner_secret = headers.get('X-Partner-Secret') or headers.get('x-partner-secret', '')

    expected_secret = os.environ.get('PARTNER_API_SECRET', '')
    if not expected_secret:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Partner integration is not configured on this server'})
        }

    if not partner_secret or not secrets.compare_digest(partner_secret, expected_secret):
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Invalid or missing X-Partner-Secret header'})
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

    login = (body_data.get('ecomkassa_login') or '').strip()
    password = body_data.get('ecomkassa_password') or ''
    partner_id = (body_data.get('partner_id') or 'default').strip()

    if not login or not password:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'ecomkassa_login and ecomkassa_password are required'})
        }

    if not re.match(r'^[A-Za-z0-9_.@-]{1,100}$', partner_id):
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Invalid partner_id format'})
        }

    ecomkassa_token = verify_ecomkassa_credentials(login, password)
    if not ecomkassa_token:
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Неверный логин или пароль ЕкомКасса'})
        }

    user_id = f'ecom_{login}'

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

    merge_orphan_accounts(cur, conn, user_id, login)

    embed_token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=EMBED_TOKEN_TTL_SECONDS)

    cur.execute(
        "INSERT INTO embed_sessions (token, user_id, partner_id, expires_at) VALUES (%s, %s, %s, %s)",
        (embed_token, user_id, partner_id, expires_at)
    )

    conn.commit()
    cur.close()
    conn.close()

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'isBase64Encoded': False,
        'body': json.dumps({
            'embed_token': embed_token,
            'embed_path': f'/embed?token={embed_token}',
            'expires_in': EMBED_TOKEN_TTL_SECONDS,
            'user_id': user_id
        })
    }
