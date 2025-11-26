import json
import os
import urllib.request
import urllib.parse
import psycopg2
from typing import Dict, Any, Optional
from datetime import datetime

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Telegram webhook для создания чеков через бота
    Args: event - dict с httpMethod, body от Telegram
          context - объект с request_id, function_name
    Returns: HTTP response dict
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
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Method not allowed'})
        }
    
    bot_token = get_bot_token()
    if not bot_token:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Bot token not configured'})
        }
    
    try:
        update = json.loads(event.get('body', '{}'))
        
        if 'message' not in update:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ok': True})
            }
        
        message = update['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')
        
        if text.startswith('/start'):
            link_code = text.replace('/start', '').strip()
            
            if link_code and link_code.startswith('LINK-'):
                result = process_link_code(link_code, chat_id)
                send_telegram_message(bot_token, chat_id, result['message'])
                return create_response({'ok': True})
            
            response_text = (
                "👋 Привет! Я помогу создавать чеки для ЕкомКасса.\n\n"
                "Просто опиши покупку, например:\n"
                "• Кофе 200р\n"
                "• Продал телефон за 15000\n"
                "• Аренда офиса 30000 наличными\n\n"
                "Я создам чек автоматически! ☕️"
            )
            send_telegram_message(bot_token, chat_id, response_text)
            return create_response({'ok': True})
        
        if text.startswith('/help'):
            response_text = (
                "📝 Как пользоваться:\n\n"
                "1. Опиши товар/услугу и сумму\n"
                "2. Я создам чек автоматически\n"
                "3. Чек отправится в ЕкомКасса\n\n"
                "Примеры:\n"
                "• Кофе латте 250р\n"
                "• Консультация 5000\n"
                "• 3 пирожка по 50р\n\n"
                "Указывай тип оплаты: наличные/карта/СБП"
            )
            send_telegram_message(bot_token, chat_id, response_text)
            return create_response({'ok': True})
        
        if text.startswith('/history'):
            user_id = get_user_id_for_telegram(chat_id)
            history = get_user_receipts_history(user_id, limit=10)
            
            if not history:
                response_text = "📋 История чеков пуста"
            else:
                response_text = "📋 Последние 10 чеков:\n\n"
                for receipt in history:
                    created_at = receipt['created_at'].strftime('%d.%m.%Y %H:%M')
                    status_emoji = '✅' if receipt['status'] == 'success' else '⚠️'
                    total = receipt['total']
                    uuid = receipt.get('uuid', 'N/A')
                    
                    items_text = ', '.join([item['name'] for item in receipt['items'][:2]])
                    if len(receipt['items']) > 2:
                        items_text += f" +{len(receipt['items']) - 2}"
                    
                    response_text += f"{status_emoji} {created_at}\n"
                    response_text += f"{items_text}\n"
                    response_text += f"💰 {total}₽ | UUID: {uuid}\n\n"
            
            send_telegram_message(bot_token, chat_id, response_text)
            return create_response({'ok': True})
        
        user_id = get_user_id_for_telegram(chat_id)
        print(f"[DEBUG] chat_id={chat_id}, resolved user_id='{user_id}'")
        
        receipt_result = process_receipt_ai(text, user_id)
        print(f"[DEBUG] receipt_result keys: {receipt_result.keys() if receipt_result else 'None'}")
        print(f"[DEBUG] receipt_result.success: {receipt_result.get('success')}")
        
        if receipt_result.get('success'):
            receipt_data = receipt_result.get('receipt', {})
            print(f"[DEBUG] receipt_data keys: {receipt_data.keys() if receipt_data else 'None'}")
            items = receipt_data.get('items', [])
            print(f"[DEBUG] items: {items}")
            total = receipt_data.get('total', 0)
            payments = receipt_data.get('payments', [])
            print(f"[DEBUG] total: {total}, payments: {payments}")
            
            # Determine payment type from payments array
            payment_type = payments[0].get('type', '1') if payments else '1'
            payment_names = {'0': "💵 Наличные", '1': "💳 Карта", '2': "📝 Предоплата", '3': "🏦 Кредит"}
            payment_str = payment_names.get(str(payment_type), "💳 Безналичный")
            
            response_text = "✅ Чек создан!\n\n"
            for item in items:
                name = item.get('name', 'Товар')
                price = item.get('price', 0)
                qty = item.get('quantity', 1)
                response_text += f"• {name} — {price}₽"
                if qty > 1:
                    response_text += f" x{qty}"
                response_text += "\n"
            
            response_text += f"\n💰 Итого: {total}₽\n{payment_str}"
            
            # Add UUID if present
            if receipt_result.get('uuid'):
                response_text += f"\n\n🆔 UUID: {receipt_result['uuid']}"
            
            print(f"[DEBUG] response_text: {response_text}")
            
        else:
            if 'message' in receipt_result:
                response_text = receipt_result['message']
            else:
                response_text = f"❌ Ошибка: {receipt_result.get('error', 'Не удалось создать чек')}"
        
        send_telegram_message(bot_token, chat_id, response_text)
        
        return create_response({'ok': True})
        
    except Exception as e:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'ok': True, 'error': str(e)})
        }


def send_telegram_message(bot_token: str, chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    urllib.request.urlopen(req, timeout=10)


def process_receipt_ai(user_message: str, user_id: str) -> Dict[str, Any]:
    process_receipt_url = 'https://functions.poehali.dev/734da785-2867-4c5d-b20c-90fc6d86b11c'
    
    payload = {
        'message': user_message,
        'operation_type': 'Приход',
        'preview_only': False,
        'external_id': f"TG_{int(datetime.now().timestamp())}",
        'settings': {}
    }
    
    try:
        req = urllib.request.Request(
            process_receipt_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'X-User-Id': user_id
            }
        )
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        try:
            error_json = json.loads(error_body)
            if 'message' in error_json:
                return {
                    'success': False,
                    'message': error_json['message']
                }
            return {
                'success': False,
                'error': error_json.get('error', f'HTTP {e.code}')
            }
        except json.JSONDecodeError:
            return {
                'success': False,
                'error': f'Ошибка AI: HTTP {e.code}'
            }
    except Exception as e:
        return {
            'success': False,
            'error': f'Ошибка AI: {str(e)}'
        }


def create_response(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'isBase64Encoded': False,
        'body': json.dumps(data)
    }


def process_link_code(link_code: str, telegram_chat_id: int) -> Dict[str, str]:
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return {'message': '❌ Ошибка сервера. Попробуйте позже.'}
    
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT user_id, expires_at, is_active FROM telegram_links WHERE link_code = %s",
            (link_code,)
        )
        result = cur.fetchone()
        
        if not result:
            return {'message': '❌ Неверный код привязки. Проверьте код в приложении.'}
        
        user_id, expires_at, is_active = result
        
        if not is_active:
            return {'message': '❌ Этот код уже использован.'}
        
        if datetime.now() > expires_at:
            return {'message': '❌ Код истёк. Получите новый в приложении.'}
        
        cur.execute(
            "UPDATE telegram_links SET telegram_chat_id = %s, linked_at = %s, is_active = FALSE WHERE link_code = %s",
            (telegram_chat_id, datetime.now(), link_code)
        )
        conn.commit()
        
        return {
            'message': (
                '✅ Telegram успешно привязан!\n\n'
                'Теперь можешь создавать чеки прямо в боте:\n'
                '• Напиши "Кофе 200р"\n'
                '• Или "Продал телефон 15000"\n\n'
                'Все чеки будут автоматически отправляться в ЕкомКасса! 🎉'
            )
        }
        
    finally:
        cur.close()
        conn.close()


def get_user_id_for_telegram(telegram_chat_id: int) -> str:
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return f"telegram_{telegram_chat_id}"
    
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    
    try:
        cur.execute(
            "SELECT user_id FROM telegram_links WHERE telegram_chat_id = %s AND is_active = FALSE ORDER BY linked_at DESC LIMIT 1",
            (telegram_chat_id,)
        )
        result = cur.fetchone()
        
        if result:
            return result[0]
        
        return f"telegram_{telegram_chat_id}"
        
    finally:
        cur.close()
        conn.close()


def get_user_receipts_history(user_id: str, limit: int = 10) -> list:
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return []
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute(
            "SELECT created_at, items, total, status, uuid "
            "FROM receipts "
            "WHERE user_id = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (user_id, limit)
        )
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        history = []
        for row in rows:
            history.append({
                'created_at': row[0],
                'items': row[1],
                'total': float(row[2]),
                'status': row[3],
                'uuid': row[4]
            })
        
        return history
    except Exception as e:
        print(f"[ERROR] Failed to load history: {e}")
        return []


def get_bot_token() -> str:
    default_token = '8367558133:AAG8btCuHLitqaRlgS_HwUsgSIRO8bZJCr0'
    
    env_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if env_token:
        return env_token
    
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return default_token
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute(
            "SELECT setting_value FROM ai_settings WHERE setting_key = 'telegram_bot_token'"
        )
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if result:
            return result[0]
        
        return default_token
    except Exception:
        return default_token