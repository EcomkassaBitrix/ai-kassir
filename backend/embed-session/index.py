import json
import os
import datetime
import psycopg2
from typing import Dict, Any


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Exchanges a one-time embed token (issued by partner-session) for the
    canonical user_id. Called by our own frontend (/embed page) right after it loads
    inside the partner's iframe. Token is single-use and short-lived.
    Args: event with httpMethod POST, body (token)
    Returns: HTTP response with user_id, ecomkassa_login or error
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
            'body': ''
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

    token = (body_data.get('token') or '').strip()
    if not token:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'token is required'})
        }

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
        "SELECT user_id, expires_at, used_at FROM embed_sessions WHERE token = %s",
        (token,)
    )
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Недействительный токен доступа'})
        }

    user_id, expires_at, used_at = row

    if used_at is not None:
        cur.close()
        conn.close()
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Токен уже был использован'})
        }

    if expires_at < datetime.datetime.utcnow():
        cur.close()
        conn.close()
        return {
            'statusCode': 401,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Токен истёк, откройте чат заново'})
        }

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

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'isBase64Encoded': False,
        'body': json.dumps({
            'user_id': user_id,
            'ecomkassa_login': ecomkassa_login or ''
        })
    }
