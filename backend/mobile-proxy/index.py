import json
import os
import datetime
import requests
import urllib3
import qrcode
import io
import base64
import psycopg2
from typing import Dict, Any, Optional, Tuple

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN_URL = 'https://app.ecomkassa.ru/fiscalorder/v5/getToken'
TOKEN_TTL_HOURS = 24


def find_session(cur, token: str) -> Optional[Tuple[str, str]]:
    '''Find user_id and password by token'''
    cur.execute(
        "SELECT s.user_id, u.ecomkassa_password FROM ecomkassa_sessions s "
        "JOIN user_settings u ON u.user_id = s.user_id "
        "WHERE s.token = %s",
        (token,)
    )
    row = cur.fetchone()
    if row:
        return row[0], row[1]
    return None


def refresh_token(cur, conn, user_id: str, login: str, password: str) -> Optional[str]:
    '''Get a fresh token from Ecomkassa and update session record'''
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

    new_token = data.get('token')
    if not new_token:
        return None

    expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_TTL_HOURS)
    cur.execute(
        "INSERT INTO ecomkassa_sessions (token, user_id, expires_at, updated_at) "
        "VALUES (%s, %s, %s, CURRENT_TIMESTAMP) "
        "ON CONFLICT (token) DO UPDATE SET "
        "user_id = EXCLUDED.user_id, expires_at = EXCLUDED.expires_at, updated_at = CURRENT_TIMESTAMP",
        (new_token, user_id, expires_at)
    )
    conn.commit()
    return new_token


def call_ecomkassa(token: str, endpoint: str, api_method: str, api_payload: Any):
    url = f'https://app.ecomkassa.ru{endpoint}'
    api_headers = {
        'Token': token,
        'Content-Type': 'application/json; charset=utf-8'
    }
    if api_method == 'POST':
        return requests.post(url, json=api_payload, headers=api_headers, timeout=10, verify=False)
    return requests.get(url, headers=api_headers, timeout=10, verify=False)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Proxy mobile app requests to Ecomkassa using stored token, silently refreshing it on expiry
    Args: event with httpMethod POST, headers X-Ecomkassa-Token, body (endpoint, method, payload)
    Returns: HTTP response with data from Ecomkassa API, X-New-Ecomkassa-Token header if token was refreshed
    '''
    method: str = event.get('httpMethod', 'GET')

    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-Ecomkassa-Token',
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

    headers_in = event.get('headers', {})
    token = headers_in.get('x-ecomkassa-token') or headers_in.get('X-Ecomkassa-Token')

    if not token:
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'X-Ecomkassa-Token header required'})
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

    endpoint = body_data.get('endpoint', '/fiscalorder/v5/default_group/sell')
    api_method = body_data.get('method', 'GET').upper()
    api_payload = body_data.get('payload')

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Database not configured'})
        }

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    session = find_session(cur, token)
    if not session:
        cur.close()
        conn.close()
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Unknown or expired token, please login again'})
        }

    user_id, password = session
    login = user_id[len('ecom_'):] if user_id.startswith('ecom_') else user_id

    try:
        response = call_ecomkassa(token, endpoint, api_method, api_payload)
    except requests.RequestException as e:
        cur.close()
        conn.close()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': f'Request failed: {str(e)}'})
        }

    new_token = None
    if response.status_code == 401:
        new_token = refresh_token(cur, conn, user_id, login, password)
        if not new_token:
            cur.close()
            conn.close()
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Failed to refresh token, please login again'})
            }
        try:
            response = call_ecomkassa(new_token, endpoint, api_method, api_payload)
        except requests.RequestException as e:
            cur.close()
            conn.close()
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': f'Request failed: {str(e)}'})
            }

    cur.close()
    conn.close()

    response_data = None
    if response.status_code == 200:
        try:
            response_data = response.json()
        except ValueError:
            response_data = None

    out_headers = {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
    if new_token:
        out_headers['X-New-Ecomkassa-Token'] = new_token

    if response_data and response_data.get('invoice_payload', {}).get('link'):
        payment_link = response_data['invoice_payload']['link']

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(payment_link)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        response_data['qr_code'] = f"data:image/png;base64,{qr_base64}"

        return {
            'statusCode': response.status_code,
            'headers': out_headers,
            'isBase64Encoded': False,
            'body': json.dumps(response_data, ensure_ascii=False)
        }

    return {
        'statusCode': response.status_code,
        'headers': out_headers,
        'isBase64Encoded': False,
        'body': response.text
    }
