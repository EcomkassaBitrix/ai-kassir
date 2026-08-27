import json
import os
from typing import Dict, Any

import psycopg2
from psycopg2.extras import RealDictCursor
import urllib.request


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Принимает вебхук от Ecomkassa об изменении статуса чека/платёжной ссылки и шлёт уведомление в Telegram при оплате
    Args: event - dict с httpMethod, body (JSON от Ecomkassa: uuid, status/invoice_payload.status, external_id)
          context - объект с request_id
    Returns: HTTP response dict с подтверждением обработки
    '''
    method: str = event.get('httpMethod', 'POST')

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

    try:
        body_data = json.loads(event.get('body') or '{}')
    except Exception:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Invalid JSON body'})
        }

    print(f"[DEBUG] Payment webhook received: {json.dumps(body_data, ensure_ascii=False)}")

    receipt_uuid = str(body_data.get('uuid', ''))
    new_status = body_data.get('invoice_payload', {}).get('status') or body_data.get('status', '')

    if not receipt_uuid or not new_status:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'success': True, 'message': 'No uuid/status, ignored'})
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
        "SELECT id, external_id, user_id, user_message, total, payment_status, payment_notified "
        "FROM receipts WHERE uuid = %s LIMIT 1",
        (receipt_uuid,)
    )
    receipt = cur.fetchone()

    if not receipt:
        cur.close()
        conn.close()
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'success': True, 'message': 'Receipt not found, ignored'})
        }

    cur.execute(
        "UPDATE receipts SET payment_status = %s, "
        "paid_at = CASE WHEN %s = 'paid' AND paid_at IS NULL THEN NOW() ELSE paid_at END, "
        "updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (new_status, new_status, receipt['id'])
    )
    conn.commit()

    if new_status == 'paid' and not receipt.get('payment_notified'):
        chat_id = get_telegram_chat_id(cur, receipt.get('user_id', ''))
        bot_token = get_bot_token(cur)

        if chat_id and bot_token:
            send_payment_notification(bot_token, chat_id, receipt)
            cur.execute(
                "UPDATE receipts SET payment_notified = true WHERE id = %s",
                (receipt['id'],)
            )
            conn.commit()

    cur.close()
    conn.close()

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({'success': True, 'status': new_status})
    }


def get_telegram_chat_id(cur, user_id: str):
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
