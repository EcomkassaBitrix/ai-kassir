import json
import os
import re
import secrets
import hashlib
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


def extract_jwt_subject(token: str) -> Optional[str]:
    '''
    Ecomkassa tokens are JWTs whose "sub" claim uniquely identifies the account that
    logged in (differs per login even within the same demo/test company where store
    lists are identical). We only read it after the token was already proven valid by
    calling Ecomkassa itself — no signature check needed, just a stable per-account key.
    '''
    import base64
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        payload_b64 = parts[1] + '=' * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        sub = payload.get('sub')
        return str(sub) if sub else None
    except Exception:
        return None


def fetch_ecomkassa_profile_by_token(token: str) -> Optional[Dict[str, Any]]:
    '''
    Validate an Ecomkassa API token directly against Ecomkassa itself (no login/password
    needed — GET /api/mobile/v1/profile/firm only needs the Token header) and return
    the raw stores payload if the token is genuine. Used as a fallback when the token
    was issued by Ecomkassa directly (e.g. partner LK's own login flow) rather than by
    our own mobile-auth endpoint, so it is not present in our ecomkassa_sessions table.
    '''
    try:
        resp = requests.get(
            'https://app.ecomkassa.ru/api/mobile/v1/profile/firm',
            headers={'Token': token, 'Content-Type': 'application/json; charset=utf-8'},
            timeout=10,
            verify=False
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    data = resp.json()
    if data.get('errorCode') != 0:
        return None

    return data.get('payload', {})


def handle_issue_from_token(body_data: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Public, no-secret flow: partner frontend already holds a real Ecomkassa API token.
    Two cases:
    1) Token was issued by OUR OWN mobile-auth endpoint (login+password once) — look it
       up in ecomkassa_sessions, instant match, no extra network call.
    2) Token was issued by Ecomkassa directly (partner's own login page calls Ecomkassa's
       getToken itself) — not in our table. Fall back to validating it straight against
       Ecomkassa (GET /api/mobile/v1/profile/firm needs only the Token header). If valid,
       cache it into ecomkassa_sessions so next time it is an instant DB match.
    '''
    ecomkassa_token = (body_data.get('ecomkassa_token') or '').strip()
    partner_id = (body_data.get('partner_id') or 'default').strip()
    shop_id = (body_data.get('shop_id') or '').strip()

    if not ecomkassa_token:
        return json_response(400, {'error': 'ecomkassa_token is required'})

    if not re.match(r'^[A-Za-z0-9_.@-]{1,100}$', partner_id):
        return json_response(400, {'error': 'Invalid partner_id format'})

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return json_response(500, {'error': 'Database not configured'})

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM ecomkassa_sessions WHERE token = %s AND expires_at > CURRENT_TIMESTAMP",
        (ecomkassa_token,)
    )
    row = cur.fetchone()

    if row:
        user_id = row[0]
    else:
        profile = fetch_ecomkassa_profile_by_token(ecomkassa_token)
        if profile is None:
            cur.close()
            conn.close()
            return json_response(401, {'error': 'Токен недействителен или истёк, войдите заново'})

        firm_id = (profile.get('firmId') or '').strip()
        tax_identity = (profile.get('taxIdentity') or '').strip()

        # IMPORTANT: profile/firm store/company data can be IDENTICAL across different
        # accounts (e.g. a shared demo/test company in Ecomkassa with several logins) — so
        # firm_id/tax_identity alone cannot safely tell two real merchants apart. The JWT
        # "sub" claim is unique per actual login, so it stays the PRIMARY identity key.
        # firm_id/tax_identity are saved alongside it purely as a resilience fallback: if
        # Ecomkassa ever changes its token format so "sub" can no longer be parsed, we can
        # still recognize a RETURNING account (one we already saved firm_id for) instead of
        # silently spawning a brand-new, disconnected user_id every time.
        jwt_subject = extract_jwt_subject(ecomkassa_token)

        user_id = None
        if jwt_subject:
            cur.execute(
                "SELECT user_id FROM user_settings WHERE ecomkassa_jwt_subject = %s LIMIT 1",
                (jwt_subject,)
            )
            subj_row = cur.fetchone()
            if subj_row:
                user_id = subj_row[0]
        elif firm_id and tax_identity:
            # jwt_subject unavailable (unexpected token format) — fall back to a firm match,
            # but only reuse an account that itself has no jwt_subject on record (meaning it
            # was created via this same fallback before), so we never merge a fallback-only
            # guess into a real, jwt-verified merchant account.
            cur.execute(
                "SELECT user_id FROM user_settings WHERE ecomkassa_firm_id = %s AND ecomkassa_tax_identity = %s "
                "AND (ecomkassa_jwt_subject IS NULL OR ecomkassa_jwt_subject = '') LIMIT 1",
                (firm_id, tax_identity)
            )
            fallback_row = cur.fetchone()
            if fallback_row:
                user_id = fallback_row[0]

        if not user_id:
            subject_key = jwt_subject or ecomkassa_token
            user_id = 'ecom_jwt_' + hashlib.sha256(subject_key.encode('utf-8')).hexdigest()[:24]

        expires_at_session = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        cur.execute(
            "INSERT INTO ecomkassa_sessions (token, user_id, expires_at, updated_at) "
            "VALUES (%s, %s, %s, CURRENT_TIMESTAMP) "
            "ON CONFLICT (token) DO UPDATE SET "
            "user_id = EXCLUDED.user_id, expires_at = EXCLUDED.expires_at, updated_at = CURRENT_TIMESTAMP",
            (ecomkassa_token, user_id, expires_at_session)
        )
        cur.execute(
            "INSERT INTO user_settings (user_id, ecomkassa_jwt_subject, ecomkassa_firm_id, ecomkassa_tax_identity, updated_at) "
            "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "ecomkassa_jwt_subject = COALESCE(NULLIF(user_settings.ecomkassa_jwt_subject, ''), EXCLUDED.ecomkassa_jwt_subject), "
            "ecomkassa_firm_id = COALESCE(NULLIF(user_settings.ecomkassa_firm_id, ''), EXCLUDED.ecomkassa_firm_id), "
            "ecomkassa_tax_identity = COALESCE(NULLIF(user_settings.ecomkassa_tax_identity, ''), EXCLUDED.ecomkassa_tax_identity), "
            "updated_at = CURRENT_TIMESTAMP",
            (user_id, jwt_subject, firm_id or None, tax_identity or None)
        )
        conn.commit()

    embed_token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=EMBED_TOKEN_TTL_SECONDS)

    cur.execute(
        "INSERT INTO embed_sessions (token, user_id, partner_id, shop_id, expires_at) VALUES (%s, %s, %s, %s, %s)",
        (embed_token, user_id, partner_id, shop_id or None, expires_at)
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
    shop_id = (body_data.get('shop_id') or '').strip()

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
        "INSERT INTO embed_sessions (token, user_id, partner_id, shop_id, expires_at) VALUES (%s, %s, %s, %s, %s)",
        (embed_token, user_id, partner_id, shop_id or None, expires_at)
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


def fetch_ecomkassa_stores_by_token(token: str) -> Optional[list]:
    '''
    GET /api/mobile/v1/profile/firm needs only a Token header — no login/password.
    (Ecomkassa/ATOL Online v5: any endpoint after auth just wants the bearer-like Token.)
    '''
    try:
        resp = requests.get(
            'https://app.ecomkassa.ru/api/mobile/v1/profile/firm',
            headers={'Token': token, 'Content-Type': 'application/json; charset=utf-8'},
            timeout=10,
            verify=False
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    data = resp.json()
    if data.get('errorCode') != 0:
        return None

    stores = data.get('payload', {}).get('stores', [])
    return [
        {
            'storeId': str(s.get('storeId', '')),
            'storeName': s.get('storeName', 'Без названия'),
            'storeAddress': s.get('storeAddress', '')
        }
        for s in stores if s.get('storeId')
    ]


def fetch_ecomkassa_stores(login: str, password: str) -> Optional[list]:
    '''Fetch the list of Ecomkassa stores (group_code candidates) for this account by re-authenticating'''
    token = verify_ecomkassa_credentials(login, password)
    if not token:
        return None
    return fetch_ecomkassa_stores_by_token(token)


def resolve_stores_for_user(cur, user_id: str, login: str, password: str) -> Optional[list]:
    '''
    Prefer a still-valid token we already issued for this user (in ecomkassa_sessions,
    populated by mobile-auth/issue_from_token) — one less round-trip to Ecomkassa, no need
    to touch the password. Falls back to a fresh login/password auth only if there is no
    usable saved token (e.g. session expired, or this account was set up via action=issue).
    '''
    cur.execute(
        "SELECT token FROM ecomkassa_sessions WHERE user_id = %s AND expires_at > CURRENT_TIMESTAMP",
        (user_id,)
    )
    session_row = cur.fetchone()
    if session_row:
        stores = fetch_ecomkassa_stores_by_token(session_row[0])
        if stores is not None:
            return stores

    if login and password:
        return fetch_ecomkassa_stores(login, password)

    return None


def handle_exchange(body_data: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Called by our own /embed frontend page right after it loads inside the partner's iframe.
    Exchanges the one-time embed token for the canonical user_id. Token is single-use and short-lived.

    Also resolves which Ecomkassa store (group_code) the chat should post receipts to:
    - If the account already has a group_code saved (returning user / previously configured
      in regular Settings) — reuse it, nothing to ask.
    - Else if the partner passed shop_id when issuing the embed token — use that directly.
    - Else if the account has exactly one store in Ecomkassa — auto-select it.
    - Else (multiple stores, no shop_id given) — return the store list so /embed can show a
      one-time picker before the chat opens; the token stays valid for a follow-up
      "select_shop" call for a few minutes.
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
        "SELECT user_id, shop_id, expires_at, used_at FROM embed_sessions WHERE token = %s",
        (token,)
    )
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return json_response(401, {'error': 'Недействительный токен доступа'})

    user_id, partner_shop_id, expires_at, used_at = row

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
        "SELECT ecomkassa_login, ecomkassa_password, group_code FROM user_settings WHERE user_id = %s",
        (user_id,)
    )
    settings_row = cur.fetchone()
    ecomkassa_login = settings_row[0] if settings_row else ''
    ecomkassa_password = settings_row[1] if settings_row else ''
    group_code = settings_row[2] if settings_row else ''

    result = {
        'user_id': user_id,
        'ecomkassa_login': ecomkassa_login or ''
    }

    if group_code:
        # Returning user (or already picked a store in regular Settings) — nothing to resolve.
        conn.commit()
        cur.close()
        conn.close()
        return json_response(200, result)

    if partner_shop_id:
        # Partner told us exactly which store to use — trust it, try to also grab its address.
        stores = resolve_stores_for_user(cur, user_id, ecomkassa_login, ecomkassa_password) or []
        matched = next((s for s in stores if s['storeId'] == partner_shop_id), None)
        cur.execute(
            "UPDATE user_settings SET group_code = %s, payment_address = COALESCE(NULLIF(payment_address, ''), %s), updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
            (partner_shop_id, matched['storeAddress'] if matched else '', user_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        return json_response(200, result)

    stores = resolve_stores_for_user(cur, user_id, ecomkassa_login, ecomkassa_password)
    if stores:
        if len(stores) == 1:
            only_store = stores[0]
            cur.execute(
                "UPDATE user_settings SET group_code = %s, payment_address = COALESCE(NULLIF(payment_address, ''), %s), updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
                (only_store['storeId'], only_store['storeAddress'], user_id)
            )
            conn.commit()
            cur.close()
            conn.close()
            return json_response(200, result)

        # Multiple stores and no hint from the partner — let the user pick once in /embed.
        conn.commit()
        cur.close()
        conn.close()
        result['needs_shop_selection'] = True
        result['shops'] = stores
        result['token'] = token
        return json_response(200, result)

    conn.commit()
    cur.close()
    conn.close()
    return json_response(200, result)


def handle_select_shop(body_data: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Follow-up call from /embed after the user picked a store from the "needs_shop_selection"
    list returned by exchange. Reuses the same (already-exchanged) embed token as proof of
    identity — valid for a short grace window after exchange so it can't be replayed later.
    '''
    token = (body_data.get('token') or '').strip()
    shop_id = (body_data.get('shop_id') or '').strip()

    if not token or not shop_id:
        return json_response(400, {'error': 'token and shop_id are required'})

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return json_response(500, {'error': 'Database not configured'})

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id, used_at FROM embed_sessions WHERE token = %s",
        (token,)
    )
    row = cur.fetchone()

    if not row or row[1] is None:
        cur.close()
        conn.close()
        return json_response(401, {'error': 'Недействительная сессия, откройте чат заново'})

    user_id, used_at = row
    grace_window = datetime.timedelta(minutes=5)
    if used_at + grace_window < datetime.datetime.utcnow():
        cur.close()
        conn.close()
        return json_response(401, {'error': 'Время выбора магазина истекло, откройте чат заново'})

    cur.execute(
        "SELECT ecomkassa_login, ecomkassa_password FROM user_settings WHERE user_id = %s",
        (user_id,)
    )
    settings_row = cur.fetchone()
    login = settings_row[0] if settings_row else ''
    password = settings_row[1] if settings_row else ''

    stores = resolve_stores_for_user(cur, user_id, login, password) or []
    matched = next((s for s in stores if s['storeId'] == shop_id), None)

    cur.execute(
        "UPDATE user_settings SET group_code = %s, payment_address = COALESCE(NULLIF(payment_address, ''), %s), updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
        (shop_id, matched['storeAddress'] if matched else '', user_id)
    )

    conn.commit()
    cur.close()
    conn.close()

    return json_response(200, {'user_id': user_id, 'group_code': shop_id})


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Combined partner-integration endpoint (four actions in one function to save
    function slots). Action "issue": partner LK backend (server-to-server) exchanges its
    X-Partner-Secret header plus Ecomkassa login/password for a one-time embed token.
    Action "issue_from_token": public, no-secret flow — partner FRONTEND sends a real
    Ecomkassa API token (obtained earlier via our public mobile-auth login) straight from
    the browser; we validate it against our own ecomkassa_sessions table and issue an embed
    token if it is genuine and not expired. Both "issue" and "issue_from_token" accept an
    optional shop_id if the partner already knows which Ecomkassa store to post receipts to.
    Action "exchange": our own /embed frontend page exchanges that embed token for the
    canonical user_id right after loading in the iframe, and also resolves which store
    (group_code) to use (saved store / partner-provided shop_id / auto-pick if the account
    has only one store / otherwise returns a shops list for the user to pick from).
    Action "select_shop": follow-up call from /embed after the user picked a store from that
    list, using the already-exchanged embed token as proof of identity.
    Args: event with httpMethod POST, body (action: "issue"|"issue_from_token"|"exchange"|"select_shop", plus action-specific fields)
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
    if action == 'issue_from_token':
        return handle_issue_from_token(body_data)
    if action == 'exchange':
        return handle_exchange(body_data)
    if action == 'select_shop':
        return handle_select_shop(body_data)

    return json_response(400, {'error': 'Missing or invalid "action" field, expected "issue", "issue_from_token", "exchange" or "select_shop"'})