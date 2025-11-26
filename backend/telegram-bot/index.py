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
        
        # Handle callback queries (button presses)
        if 'callback_query' in update:
            return handle_callback_query(update['callback_query'], bot_token)
        
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
        
        # Get preview of the receipt
        preview_result = process_receipt_ai(text, user_id, preview_only=True)
        print(f"[DEBUG] preview_result: {preview_result.get('success')}, preview: {preview_result.get('preview')}")
        
        if preview_result.get('preview'):
            receipt_data = preview_result.get('receipt', {})
            items = receipt_data.get('items', [])
            total = receipt_data.get('total', 0)
            payments = receipt_data.get('payments', [])
            client_data = receipt_data.get('client', {})
            operation_type = preview_result.get('operation_type', 'sell')
            
            # Operation type names
            operation_names = {
                'sell': '🛒 Приход (продажа)',
                'refund': '↩️ Возврат прихода',
                'sell_correction': '📝 Коррекция прихода',
                'refund_correction': '📝 Коррекция расхода'
            }
            
            response_text = "📋 <b>Проверь чек перед отправкой:</b>\n\n"
            response_text += f"<b>Тип операции:</b> {operation_names.get(operation_type, operation_type)}\n\n"
            
            # Items with all details
            response_text += "<b>Товары/Услуги:</b>\n"
            for idx, item in enumerate(items, 1):
                name = item.get('name', 'Товар')
                price = item.get('price', 0)
                qty = item.get('quantity', 1)
                measure = item.get('measure', 'шт')
                vat = item.get('vat', 'none')
                payment_method = item.get('payment_method', 'full_payment')
                payment_object = item.get('payment_object', 'commodity')
                
                # VAT names
                vat_names = {
                    'none': 'Без НДС',
                    'vat0': 'НДС 0%',
                    'vat10': 'НДС 10%',
                    'vat20': 'НДС 20%'
                }
                
                # Payment method names
                method_names = {
                    'full_payment': 'Полный расчёт',
                    'prepayment': 'Предоплата',
                    'advance': 'Аванс',
                    'full_prepayment': 'Предоплата 100%',
                    'partial_payment': 'Частичный расчёт',
                    'credit': 'Кредит',
                    'credit_payment': 'Оплата кредита'
                }
                
                # Payment object names
                object_names = {
                    'commodity': 'Товар',
                    'service': 'Услуга',
                    'excise': 'Подакцизный товар',
                    'job': 'Работа'
                }
                
                response_text += f"\n<b>{idx}. {name}</b>\n"
                response_text += f"   Цена: {price}₽ × {qty} {measure}\n"
                response_text += f"   НДС: {vat_names.get(vat, vat)}\n"
                response_text += f"   Предмет: {object_names.get(payment_object, payment_object)}\n"
                response_text += f"   Способ: {method_names.get(payment_method, payment_method)}\n"
            
            # Payment details
            response_text += f"\n<b>💰 Итого:</b> {total}₽\n\n"
            
            if payments and len(payments) > 1:
                response_text += "<b>Способы оплаты:</b>\n"
                payment_names = {'0': "💵 Наличные", '1': "💳 Безналичный", '2': "📝 Предоплата", '3': "🏦 Кредит", '4': "⚡ Иное"}
                for payment in payments:
                    ptype = payment.get('type', '1')
                    psum = payment.get('sum', 0)
                    response_text += f"  • {payment_names.get(str(ptype), 'Безнал')}: {psum}₽\n"
            else:
                payment_type = payments[0].get('type', '1') if payments else '1'
                payment_names = {'0': "💵 Наличные", '1': "💳 Безналичный", '2': "📝 Предоплата", '3': "🏦 Кредит", '4': "⚡ Иное"}
                payment_str = payment_names.get(str(payment_type), "💳 Безналичный")
                response_text += f"<b>Способ оплаты:</b> {payment_str}\n"
            
            # Client info
            response_text += f"\n<b>📧 Email клиента:</b> {client_data.get('email', 'Не указан')}\n"
            
            client_phone = client_data.get('phone')
            if client_phone:
                response_text += f"<b>📱 Телефон:</b> {client_phone}\n"
            
            # Save preview data to send with callback
            preview_id = save_preview_data(chat_id, text, user_id)
            
            # Send with inline keyboard
            send_telegram_message_with_buttons(
                bot_token, 
                chat_id, 
                response_text,
                [
                    [{"text": "✅ Отправить чек", "callback_data": f"confirm_{preview_id}"}],
                    [{"text": "❌ Отменить", "callback_data": f"cancel_{preview_id}"}]
                ]
            )
            
        else:
            if 'message' in preview_result:
                response_text = preview_result['message']
            else:
                response_text = f"❌ Ошибка: {preview_result.get('error', 'Не удалось создать чек')}"
            
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


def send_telegram_message_with_buttons(bot_token: str, chat_id: int, text: str, buttons: list) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'reply_markup': {
            'inline_keyboard': buttons
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    urllib.request.urlopen(req, timeout=10)


def process_receipt_ai(user_message: str, user_id: str, preview_only: bool = False) -> Dict[str, Any]:
    process_receipt_url = 'https://functions.poehali.dev/734da785-2867-4c5d-b20c-90fc6d86b11c'
    
    payload = {
        'message': user_message,
        'operation_type': 'Приход',
        'preview_only': preview_only,
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


def handle_callback_query(callback_query: Dict[str, Any], bot_token: str) -> Dict[str, Any]:
    query_id = callback_query['id']
    chat_id = callback_query['message']['chat']['id']
    message_id = callback_query['message']['message_id']
    callback_data = callback_query['data']
    
    # Answer callback query to remove loading state
    answer_url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    answer_req = urllib.request.Request(
        answer_url,
        data=json.dumps({'callback_query_id': query_id}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(answer_req, timeout=5)
    
    if callback_data.startswith('confirm_'):
        preview_id = callback_data.replace('confirm_', '')
        preview_data = get_preview_data(preview_id)
        
        if not preview_data:
            edit_message(bot_token, chat_id, message_id, "❌ Ошибка: данные не найдены")
            return create_response({'ok': True})
        
        user_message = preview_data['user_message']
        user_id = preview_data['user_id']
        
        # Create actual receipt
        receipt_result = process_receipt_ai(user_message, user_id, preview_only=False)
        
        if receipt_result.get('success'):
            receipt_data = receipt_result.get('receipt', {})
            items = receipt_data.get('items', [])
            total = receipt_data.get('total', 0)
            payments = receipt_data.get('payments', [])
            
            payment_type = payments[0].get('type', '1') if payments else '1'
            payment_names = {'0': "💵 Наличные", '1': "💳 Карта", '2': "📝 Предоплата", '3': "🏦 Кредит"}
            payment_str = payment_names.get(str(payment_type), "💳 Безналичный")
            
            response_text = "✅ Чек создан и отправлен!\n\n"
            for item in items:
                name = item.get('name', 'Товар')
                price = item.get('price', 0)
                qty = item.get('quantity', 1)
                response_text += f"• {name} — {price}₽"
                if qty > 1:
                    response_text += f" x{qty}"
                response_text += "\n"
            
            response_text += f"\n💰 Итого: {total}₽\n{payment_str}"
            
            if receipt_result.get('uuid'):
                response_text += f"\n\n🆔 UUID: {receipt_result['uuid']}"
            
            edit_message(bot_token, chat_id, message_id, response_text)
        else:
            error_msg = receipt_result.get('message') or receipt_result.get('error', 'Не удалось создать чек')
            edit_message(bot_token, chat_id, message_id, f"❌ Ошибка: {error_msg}")
        
        delete_preview_data(preview_id)
        
    elif callback_data.startswith('cancel_'):
        preview_id = callback_data.replace('cancel_', '')
        edit_message(bot_token, chat_id, message_id, "❌ Создание чека отменено")
        delete_preview_data(preview_id)
    
    return create_response({'ok': True})


def edit_message(bot_token: str, chat_id: int, message_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    data = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[ERROR] Failed to edit message: {e}")


def save_preview_data(chat_id: int, user_message: str, user_id: str) -> str:
    import time
    preview_id = f"{chat_id}_{int(time.time())}"
    
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return preview_id
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute(
            "CREATE TABLE IF NOT EXISTS telegram_previews ("
            "preview_id TEXT PRIMARY KEY, "
            "chat_id BIGINT, "
            "user_message TEXT, "
            "user_id TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        
        cur.execute(
            "INSERT INTO telegram_previews (preview_id, chat_id, user_message, user_id) "
            "VALUES (%s, %s, %s, %s)",
            (preview_id, chat_id, user_message, user_id)
        )
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Failed to save preview: {e}")
    
    return preview_id


def get_preview_data(preview_id: str) -> Optional[Dict[str, Any]]:
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return None
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute(
            "SELECT user_message, user_id FROM telegram_previews WHERE preview_id = %s",
            (preview_id,)
        )
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result:
            return {
                'user_message': result[0],
                'user_id': result[1]
            }
        
        return None
    except Exception as e:
        print(f"[ERROR] Failed to get preview: {e}")
        return None


def delete_preview_data(preview_id: str) -> None:
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute("DELETE FROM telegram_previews WHERE preview_id = %s", (preview_id,))
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Failed to delete preview: {e}")


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