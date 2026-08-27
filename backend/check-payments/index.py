import json
import os
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Опрашивает Ecomkassa по всем неоплаченным платёжным ссылкам и шлёт уведомление в Telegram, когда клиент оплатил счёт
    Args: event - dict с httpMethod, headers (X-Cron-Token для авторизации внешнего планировщика)
          context - объект с request_id
    Returns: HTTP response dict со сводкой проверки (сколько проверено, сколько оплачено)
    '''
    method: str = event.get('httpMethod', 'GET')

    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-Cron-Token',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }

    headers_in = event.get('headers') or {}
    provided_token = headers_in.get('X-Cron-Token') or headers_in.get('x-cron-token', '')
    expected_token = os.environ.get('CRON_SECRET_TOKEN', '')

    if not expected_token or provided_token != expected_token:
        return {
            'statusCode': 403,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Forbidden: invalid or missing X-Cron-Token'})
        }

    database_url = os.environ.get('DATABASE_URL', '')
    if not database_url:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Database not configured'})
        }

    conn = psycopg2.connect(database_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        "SELECT id, external_id, uuid, user_id, user_message, total, ecomkassa_response, payment_status "
        "FROM receipts "
        "WHERE demo_mode = false "
        "AND uuid IS NOT NULL "
        "AND ecomkassa_response -> 'invoice_payload' IS NOT NULL "
        "AND COALESCE(payment_status, 'wait') = 'wait' "
        "AND created_at > NOW() - INTERVAL '3 days' "
        "ORDER BY created_at DESC "
        "LIMIT 100"
    )
    pending_receipts = cur.fetchall()

    checked = 0
    paid_now: List[Dict[str, Any]] = []
    errors: List[str] = []

    settings_cache: Dict[str, Optional[Dict[str, str]]] = {}
    bot_token = get_bot_token(cur)

    for receipt in pending_receipts:
        checked += 1
        user_id = receipt.get('user_id') or ''

        if user_id not in settings_cache:
            settings_cache[user_id] = load_user_credentials(cur, user_id)
        creds = settings_cache[user_id]

        if not creds or not creds.get('ecomkassa_login') or not creds.get('ecomkassa_password'):
            continue

        token = get_ecomkassa_token(creds['ecomkassa_login'], creds['ecomkassa_password'])
        if not token:
            errors.append(f"auth_failed:{receipt['external_id']}")
            continue

        group_code = creds.get('group_code', '')
        status_info = get_ecomkassa_report(receipt['uuid'], token, group_code)

        if not status_info:
            errors.append(f"status_failed:{receipt['external_id']}")
            continue

        new_status = status_info.get('status', 'wait')

        if new_status == receipt.get('payment_status'):
            continue

        cur.execute(
            "UPDATE receipts SET payment_status = %s, paid_at = CASE WHEN %s = 'paid' THEN NOW() ELSE paid_at END, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (new_status, new_status, receipt['id'])
        )
        conn.commit()

        if new_status == 'paid':
            chat_id = get_telegram_chat_id(cur, user_id)
            if chat_id and bot_token:
                send_payment_notification(bot_token, chat_id, receipt)
                cur.execute(
                    "UPDATE receipts SET payment_notified = true WHERE id = %s",
                    (receipt['id'],)
                )
                conn.commit()
            paid_now.append({'external_id': receipt['external_id'], 'total': float(receipt['total'])})

    cur.close()
    conn.close()

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({
            'success': True,
            'checked': checked,
            'paid': paid_now,
            'errors': errors
        })
    }


def load_user_credentials(cur, user_id: str) -> Optional[Dict[str, str]]:
    if not user_id:
        return None
    cur.execute(
        "SELECT ecomkassa_login, ecomkassa_password, group_code FROM user_settings WHERE user_id = %s LIMIT 1",
        (user_id,)
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        'ecomkassa_login': row.get('ecomkassa_login') or os.environ.get('ECOMKASSA_LOGIN', ''),
        'ecomkassa_password': row.get('ecomkassa_password') or os.environ.get('ECOMKASSA_PASSWORD', ''),
        'group_code': row.get('group_code') or os.environ.get('ECOMKASSA_GROUP_CODE', '')
    }


def get_ecomkassa_token(login: str, password: str) -> Optional[str]:
    auth_url = 'https://app.ecomkassa.ru/fiscalorder/v5/getToken'
    payload = {'login': login, 'pass': password}
    try:
        req = urllib.request.Request(
            auth_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json; charset=utf-8'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get('code') == 0:
                return data.get('token')
            return None
    except Exception:
        return None


def get_ecomkassa_report(receipt_uuid: str, token: str, group_code: str) -> Optional[Dict[str, Any]]:
    '''Запрашивает у Ecomkassa текущий статус чека/платёжной ссылки по uuid'''
    url = f'https://app.ecomkassa.ru/fiscalorder/v5/{group_code}/report/{receipt_uuid}'
    try:
        req = urllib.request.Request(
            url,
            headers={'Token': token, 'Content-Type': 'application/json; charset=utf-8'},
            method='GET'
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            invoice_status = data.get('invoice_payload', {}).get('status') or data.get('status', 'wait')
            return {'status': invoice_status, 'raw': data}
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None


def get_telegram_chat_id(cur, user_id: str) -> Optional[int]:
    if not user_id:
        return None
    cur.execute(
        "SELECT telegram_chat_id FROM telegram_links WHERE user_id = %s AND telegram_chat_id IS NOT NULL "
        "ORDER BY linked_at DESC NULLS LAST LIMIT 1",
        (user_id,)
    )
    row = cur.fetchone()
    return row.get('telegram_chat_id') if row else None


def get_bot_token(cur) -> str:
    env_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if env_token:
        return env_token
    try:
        cur.execute("SELECT setting_value FROM ai_settings WHERE setting_key = 'telegram_bot_token'")
        row = cur.fetchone()
        if row:
            return row.get('setting_value', '')
    except Exception:
        pass
    return ''


def send_payment_notification(bot_token: str, chat_id: int, receipt: Dict[str, Any]) -> None:
    total = receipt.get('total')
    external_id = receipt.get('external_id', '')
    user_message = receipt.get('user_message', '')

    text = (
        f"💰 <b>Оплата поступила!</b>\n\n"
        f"Счёт: {user_message}\n"
        f"Сумма: {total}₽\n"
        f"№ {external_id}"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}

    for attempt in range(2):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req, timeout=5)
            return
        except Exception:
            continue
