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
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '8367558133:AAG8btCuHLitqaRlgS_HwUsgSIRO8bZJCr0')
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
        
        user_id = get_user_id_for_telegram(chat_id)
        
        receipt_result = process_receipt_ai(text, user_id)
        
        if receipt_result['success']:
            receipt_data = receipt_result['data']
            items = receipt_data.get('items', [])
            total = receipt_data.get('Total', 0)
            payment_type = receipt_data.get('PaymentType', 1)
            
            payment_names = {1: "💵 Наличные", 2: "💳 Карта", 3: "💰 СБП"}
            payment_str = payment_names.get(payment_type, "Оплата")
            
            response_text = "✅ Чек создан!\n\n"
            for item in items:
                name = item.get('Name', 'Товар')
                price = item.get('Price', 0)
                qty = item.get('Quantity', 1)
                response_text += f"• {name} — {price}₽ x{qty}\n"
            
            response_text += f"\n💰 Итого: {total}₽\n{payment_str}"
            
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