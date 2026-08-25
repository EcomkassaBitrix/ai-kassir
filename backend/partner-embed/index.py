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


def cors_headers(extra_allow_headers: str = '') -> Dict[str, str]:
    allow_headers = 'Content-Type, X-Partner-Secret'
    if extra_allow_headers:
        allow_headers += f', {extra_allow_headers}'
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': allow_headers,
        'Access-Control-Max-Age': '86400'
    }


def json_response(status: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'isBase64Encoded': False,
        'body': json.dumps(payload)
    }


def handle_issue(body_data: Dict[str, Any], headers: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Server-to-server: partner backend exchanges its secret + Ecomkassa login/password
    for a one-time embed token used to open the AI cashier chat in an iframe.
    '''
    partner_secret = headers.get('X-Partner-Secret') or headers.get('x-partner-secret', '')

    expected_secret = os.environ.get('PARTNER_API_SECRET', '')
    if not expected_secret:
        return json_response(500, {'error': 'Partner integration is not configured on this server'})

    if not partner_secret or not secrets.compare_digest(partner_secret, expected_secret):
        return json_response(401, {'error': 'Invalid or missing X-Partner-Secret header'})

    login = (body_data.get('ecomkassa_login') or '').strip()
    password = body_data.get('ecomkassa_password') or ''
    partner_id = (body_data.get('partner_id') or 'default').strip()

    if not login or not password:
        return json_response(400, {'error': 'ecomkassa_login and ecomkassa_password are required'})

    if not re.match(r'^[A-Za-z0-9_.@-]{1,100}$', partner_id):
        return json_response(400, {'error': 'Invalid partner_id format'})

    ecomkassa_token = verify_ecomkassa_credentials(login, password)
    if not ecomkassa_token:
        return json_response(401, {'error': 'Неверный логин или пароль ЕкомКасса'})

    user_id = f'ecom_{login}'

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return json_response(500, {'error': 'Database not configured'})

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

    return json_response(200, {
        'embed_token': embed_token,
        'embed_path': f'/embed?token={embed_token}',
        'expires_in': EMBED_TOKEN_TTL_SECONDS,
        'user_id': user_id
    })


def handle_exchange(body_data: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Called by our own /embed frontend page right after it loads inside the partner's iframe.
    Exchanges the one-time embed token for the canonical user_id. Token is single-use and short-lived.
    '''
    token = (body_data.get('token') or '').strip()
    if not token:
        return json_response(400, {'error': 'token is required'})

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return json_response(500, {'error': 'Database not configured'})

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id, expires_at, used_at FROM embed_sessions WHERE token = %s",
        (token,)
    )
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return json_response(401, {'error': 'Недействительный токен доступа'})

    user_id, expires_at, used_at = row

    if used_at is not None:
        cur.close()
        conn.close()
        return json_response(401, {'error': 'Токен уже был использован'})

    if expires_at < datetime.datetime.utcnow():
        cur.close()
        conn.close()
        return json_response(401, {'error': 'Токен истёк, откройте чат заново'})

    cur.execute(
        "UPDATE embed_sessions SET used_at = CURRENT_TIMESTAMP WHERE token = %s",
        (token,)
    )

    cur.execute(
        "SELECT ecomkassa_login FROM user_settings WHERE user_id = %s",
        (user_id,)
    )
    settings_row = cur.fetchone()
    ecomkassa_login = settings_row[0] if settings_row else ''

    conn.commit()
    cur.close()
    conn.close()

    return json_response(200, {
        'user_id': user_id,
        'ecomkassa_login': ecomkassa_login or ''
    })


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Combined partner-integration endpoint (two actions in one function to save
    a function slot). Action "issue": partner LK backend exchanges X-Partner-Secret header
    plus Ecomkassa login/password for a one-time embed token. Action "exchange": our own
    /embed frontend page exchanges that token for the canonical user_id right after loading
    inside the partner's iframe.
    Args: event with httpMethod POST, body (action: "issue"|"exchange", plus action-specific fields)
    Returns: HTTP response with token/user data depending on requested action
    '''
    method: str = event.get('httpMethod', 'GET')

    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': ''
        }

    if method != 'POST':
        return json_response(405, {'error': 'Method not allowed'})

    headers = event.get('headers', {})
    body_str = event.get('body', '')
    try:
        body_data = json.loads(body_str) if body_str else {}
    except json.JSONDecodeError:
        return json_response(400, {'error': 'Invalid JSON'})

    action = (body_data.get('action') or '').strip().lower()

    if action == 'issue':
        return handle_issue(body_data, headers)
    if action == 'exchange':
        return handle_exchange(body_data)

    return json_response(400, {'error': 'Missing or invalid "action" field, expected "issue" or "exchange"'})
