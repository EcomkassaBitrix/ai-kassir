import json
import os
import urllib.request
import urllib.error
import psycopg2
import psycopg2.extras
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime


def get_db_connection():
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        raise ValueError("DATABASE_URL not configured")
    return psycopg2.connect(dsn)


def execute_query(query: str, params=None, fetch_one=False, fetch_all=False, commit=False):
    conn = get_db_connection()
    cur = conn.cursor()
    
    schema = 't_p7891941_voice_ai_agent_1'
    tables_to_prefix = ['bot_settings', 'telegram_users', 'receipts', 'editing_previews', 
                        'chat_contexts', 'telegram_link_codes', 'ai_settings', 'user_settings']
    modified_query = query
    
    for table in tables_to_prefix:
        if table in modified_query and f'{schema}.{table}' not in modified_query:
            import re
            pattern = r'\b' + table + r'\b'
            modified_query = re.sub(pattern, f'{schema}.{table}', modified_query)
    
    try:
        cur.execute(modified_query, params)
    except Exception as e:
        print(f"[ERROR] Query failed: {str(e)[:200]}")
        print(f"[ERROR] Query was: {modified_query[:300]}")
        raise
    
    result = None
    if fetch_one:
        result = cur.fetchone()
    elif fetch_all:
        result = cur.fetchall()
    
    if commit:
        conn.commit()
    
    cur.close()
    conn.close()
    return result


def get_bot_token() -> Optional[str]:
    try:
        row = execute_query(
            "SELECT setting_value FROM bot_settings WHERE setting_key = 'telegram_bot_token'",
            fetch_one=True
        )
        return row[0] if row else None
    except Exception as e:
        print(f"[ERROR] Failed to get bot token: {e}")
        return None


def get_ai_settings() -> Optional[Dict[str, Any]]:
    try:
        row = execute_query(
            "SELECT gptunnel_api_key, yandex_speechkit_key, text_provider, voice_provider FROM ai_settings LIMIT 1",
            fetch_one=True
        )
        if not row:
            return None
        return {
            'gptunnel_key': row[0],
            'yandex_key': row[1],
            'text_provider': row[2],
            'voice_provider': row[3]
        }
    except Exception as e:
        print(f"[ERROR] Failed to get AI settings: {e}")
        return None


def get_user_settings(user_id: str) -> Optional[Dict[str, Any]]:
    try:
        row = execute_query("""
            SELECT group_code, inn, sno, default_vat, company_email, payment_address,
                   ecomkassa_login, ecomkassa_password
            FROM user_settings WHERE user_id = %s LIMIT 1
        """, (user_id,), fetch_one=True)
        
        if not row:
            return None
        return {
            'group_code': row[0],
            'inn': row[1],
            'sno': row[2],
            'default_vat': row[3],
            'company_email': row[4],
            'payment_address': row[5],
            'ecomkassa_login': row[6],
            'ecomkassa_password': row[7]
        }
    except Exception as e:
        print(f"[ERROR] Failed to get user settings: {e}")
        return None


def get_user_id_for_telegram(telegram_lookup_id: str) -> Optional[str]:
    row = execute_query(
        "SELECT user_id FROM telegram_users WHERE telegram_lookup_id = %s",
        (telegram_lookup_id,),
        fetch_one=True
    )
    return row[0] if row else None


def parse_receipt_with_ai(text: str, user_settings: Dict[str, Any], context: Optional[str] = None) -> Dict[str, Any]:
    ai_settings = get_ai_settings()
    if not ai_settings or not ai_settings.get('gptunnel_key'):
        raise ValueError("GPTunnel API key not configured")
    
    context_part = f"\n\nКонтекст предыдущего запроса: \"{context}\"\n\nВАЖНО: Если новый запрос содержит только недостающие данные, объедини их с контекстом." if context else ""
    
    prompt = f"""Ты ИИ кассир. Преобразуй запрос в JSON чека по API Ecomkassa.

Запрос: "{text}"{context_part}

КРИТИЧНО:
- name (название): ОБЯЗАТЕЛЬНО. НИКОГДА не подставляй "товар", "услуга" - спрашивай через error
- price (цена): ОБЯЗАТЕЛЬНА. Если нет - спрашивай через error
- email/phone: НЕ обязательны, можно null

payment_object: 
- service: психолог, консультация, стрижка, массаж, урок, уборка, доставка, аренда
- commodity: кофе, телефон, мебель, одежда, еда

payment_method: full_payment (по умолчанию)

Формат:
{{"operation_type":"sell","items":[{{"name":"товар","price":100,"quantity":1,"measure":"шт","vat":"none","payment_method":"full_payment","payment_object":"commodity"}}],"client":{{"email":null,"phone":null}},"payments":[{{"type":"1","sum":100}}]}}

Если НЕ ХВАТАЕТ ДАННЫХ - верни error:
{{"error":"Не хватает данных: укажи цену. Пример: кофе 200₽"}}

ВАЖНО: Сумма всех payments = сумма items. Отвечай только JSON без пояснений."""
    
    url = "https://gptunnel.ru/v1/chat/completions"
    data = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.3
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json', 
        'Authorization': f'Bearer {ai_settings["gptunnel_key"]}'
    })
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
    
    content = result['choices'][0]['message']['content']
    parsed_data = json.loads(content)
    
    if 'error' in parsed_data:
        return parsed_data
    
    if 'items' not in parsed_data or not parsed_data['items']:
        return {'error': 'Не могу распознать товары. Укажи название и цену. Пример: кофе 200₽'}
    
    total = sum(item['price'] * item.get('quantity', 1) for item in parsed_data['items'])
    parsed_data['total'] = round(total, 2)
    
    return parsed_data


def transcribe_voice_with_yandex(audio_bytes: bytes) -> str:
    ai_settings = get_ai_settings()
    if not ai_settings or not ai_settings.get('yandex_key'):
        raise ValueError("Yandex SpeechKit API key not configured")
    
    url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    params = "?lang=ru-RU&format=oggopus&sampleRateHertz=48000"
    
    req = urllib.request.Request(
        url + params,
        data=audio_bytes,
        headers={'Authorization': f'Api-Key {ai_settings["yandex_key"]}'}
    )
    
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
    
    return result.get('result', '')


def save_receipt_to_db(user_id: str, receipt_data: Dict[str, Any], telegram_chat_id: int, telegram_message_id: int, user_message: str) -> int:
    external_id = f'telegram_{telegram_chat_id}_{telegram_message_id}'
    row = execute_query("""
        INSERT INTO receipts (
            user_id, uuid, external_id, user_message, items, total, payment_type, status, 
            operation_type, demo_mode, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        user_id,
        str(uuid.uuid4()),
        external_id,
        user_message,
        psycopg2.extras.Json(receipt_data['items']),
        receipt_data['total'],
        receipt_data.get('payments', [{}])[0].get('type', '1'),
        'pending',
        receipt_data.get('operation_type', 'sell'),
        False,
        datetime.now(),
        datetime.now()
    ), fetch_one=True, commit=True)
    return row[0]


def send_telegram_message(bot_token: str, chat_id: int, text: str, buttons: Optional[List[List[Dict[str, str]]]] = None) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if buttons:
        payload['reply_markup'] = {'inline_keyboard': buttons}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as response:
        response.read()


def edit_telegram_message(bot_token: str, chat_id: int, message_id: int, text: str, buttons: Optional[List[List[Dict[str, str]]]] = None) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload = {'chat_id': chat_id, 'message_id': message_id, 'text': text, 'parse_mode': 'HTML'}
    if buttons:
        payload['reply_markup'] = {'inline_keyboard': buttons}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            response.read()
    except Exception as e:
        print(f"[ERROR] Failed to edit message: {e}")


def download_telegram_file(bot_token: str, file_id: str) -> bytes:
    get_file_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
    with urllib.request.urlopen(get_file_url) as response:
        file_info = json.loads(response.read().decode('utf-8'))
    file_path = file_info['result']['file_path']
    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    with urllib.request.urlopen(download_url) as response:
        return response.read()


def format_receipt_message(receipt_data: Dict[str, Any], receipt_id: int) -> str:
    items_text = []
    for item in receipt_data['items']:
        name = item['name']
        price = item['price']
        qty = item.get('quantity', 1)
        total = price * qty
        items_text.append(f"  • {name} — {price}₽ × {qty} = {total}₽" if qty > 1 else f"  • {name} — {price}₽")
    
    payment_type = receipt_data.get('payments', [{}])[0].get('type', '1')
    payment_emoji = "💳" if payment_type == '1' else "💵"
    payment_text = "Карта" if payment_type == '1' else "Наличные"
    short_uuid = str(receipt_id)[:8]
    
    return (f"🧾 <b>Чек #{short_uuid}</b>\n\n<b>Позиции:</b>\n" + "\n".join(items_text) +
            f"\n\n<b>Итого:</b> {receipt_data['total']}₽\n{payment_emoji} <b>Оплата:</b> {payment_text}\n\n✅ Чек создан!")


def create_receipt_buttons(receipt_id: int) -> List[List[Dict[str, str]]]:
    return [
        [{"text": "🔄 Повторить", "callback_data": f"repeat_{receipt_id}"},
         {"text": "✏️ Изменить", "callback_data": f"edit_{receipt_id}"}]
    ]


def save_context(chat_id: int, context_data: Dict[str, Any]) -> None:
    execute_query("""
        INSERT INTO chat_contexts (chat_id, context_data, updated_at)
        VALUES (%s, %s, %s) ON CONFLICT (chat_id)
        DO UPDATE SET context_data = EXCLUDED.context_data, updated_at = EXCLUDED.updated_at
    """, (chat_id, psycopg2.extras.Json(context_data), datetime.now()), commit=True)


def get_context(chat_id: int) -> Optional[Dict[str, Any]]:
    row = execute_query("SELECT context_data FROM chat_contexts WHERE chat_id = %s", (chat_id,), fetch_one=True)
    return row[0] if row else None


def clear_context(chat_id: int) -> None:
    execute_query("DELETE FROM chat_contexts WHERE chat_id = %s", (chat_id,), commit=True)


def handle_receipt_creation(text: str, chat_id: int, message_id: int, user_id: str, bot_token: str) -> None:
    context = get_context(chat_id)
    context_text = context.get('last_incomplete_request') if context else None
    
    print(f"[INFO] Creating receipt for chat {chat_id}, text: {text[:50]}...")
    
    try:
        user_settings = get_user_settings(user_id)
        if not user_settings:
            send_telegram_message(bot_token, chat_id, "❌ Настройки пользователя не найдены. Зайди в веб-интерфейс и настрой интеграцию с Екомкасса")
            return
        
        receipt_data = parse_receipt_with_ai(text, user_settings, context_text)
        print(f"[INFO] AI parsed receipt: {receipt_data}")
        
        if 'error' in receipt_data:
            send_telegram_message(bot_token, chat_id, f"❓ {receipt_data['error']}\n\nОтправь недостающие данные или напиши 'отмена'")
            save_context(chat_id, {'last_incomplete_request': text})
            return
        
        receipt_id = save_receipt_to_db(user_id, receipt_data, chat_id, message_id, text)
        message_text = format_receipt_message(receipt_data, receipt_id)
        buttons = create_receipt_buttons(receipt_id)
        
        send_telegram_message(bot_token, chat_id, message_text, buttons)
        clear_context(chat_id)
        print(f"[INFO] Receipt {receipt_id} created successfully")
        
    except Exception as e:
        print(f"[ERROR] Receipt creation failed: {e}")
        send_telegram_message(bot_token, chat_id, f"❌ Ошибка создания чека: {str(e)}")
        clear_context(chat_id)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    method = event.get('httpMethod', 'POST')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }
    
    if method == 'GET':
        bot_token = get_bot_token()
        if not bot_token:
            return {'statusCode': 500, 'body': json.dumps({'error': 'Bot token not configured'})}
        
        webhook_url = 'https://functions.poehali.dev/c931c0bd-bad6-4f16-9a76-f67296c311b1'
        telegram_api_url = f'https://api.telegram.org/bot{bot_token}/setWebhook?url={webhook_url}'
        
        try:
            req = urllib.request.Request(telegram_api_url, method='POST')
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())
                return {'statusCode': 200, 'body': json.dumps({'success': True, 'webhook_set': result})}
        except Exception as e:
            return {'statusCode': 500, 'body': json.dumps({'error': f'Failed to set webhook: {str(e)}'})}
    
    if method != 'POST':
        return {'statusCode': 405, 'body': json.dumps({'error': 'Method not allowed'})}
    
    bot_token = get_bot_token()
    if not bot_token:
        return {'statusCode': 500, 'body': json.dumps({'error': 'Bot token not configured'})}
    
    try:
        update = json.loads(event.get('body', '{}'))
        print(f"[INFO] Received update: {json.dumps(update)[:200]}")
        
        if 'message' not in update:
            return {'statusCode': 200, 'body': json.dumps({'ok': True})}
        
        message = update['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')
        
        if 'voice' in message:
            send_telegram_message(bot_token, chat_id, "🎤 Распознаю голос...")
            try:
                voice = message['voice']
                file_id = voice['file_id']
                audio_data = download_telegram_file(bot_token, file_id)
                text = transcribe_voice_with_yandex(audio_data)
                send_telegram_message(bot_token, chat_id, f"✅ Распознано: \"{text}\"\n\nОбрабатываю...")
            except Exception as e:
                send_telegram_message(bot_token, chat_id, f"❌ Ошибка распознавания: {str(e)}")
                return {'statusCode': 200, 'body': json.dumps({'ok': True})}
        
        lookup_id = f"telegram_{chat_id}"
        user_id = get_user_id_for_telegram(lookup_id)
        
        if not user_id:
            print(f"[WARN] User not found for lookup_id: {lookup_id}")
            send_telegram_message(bot_token, chat_id, "❌ Пользователь не найден. Отправь /start с кодом привязки")
            return {'statusCode': 200, 'body': json.dumps({'ok': True})}
        
        print(f"[INFO] Processing message from user {user_id}, chat {chat_id}, text: {text[:50]}...")
        
        if text.lower() in ['отмена', 'отменить', 'cancel']:
            clear_context(chat_id)
            send_telegram_message(bot_token, chat_id, "✅ Контекст очищен. Можешь начать заново")
            return {'statusCode': 200, 'body': json.dumps({'ok': True})}
        
        if text.startswith('/start'):
            link_code = text.replace('/start', '').strip()
            
            if link_code and link_code.startswith('LINK-'):
                row = execute_query("SELECT user_id FROM telegram_link_codes WHERE code = %s AND used = false", (link_code,), fetch_one=True)
                
                if row:
                    linked_user_id = row[0]
                    execute_query("INSERT INTO telegram_users (telegram_lookup_id, user_id) VALUES (%s, %s) ON CONFLICT (telegram_lookup_id) DO UPDATE SET user_id = EXCLUDED.user_id", (lookup_id, linked_user_id), commit=True)
                    execute_query("UPDATE telegram_link_codes SET used = true WHERE code = %s", (link_code,), commit=True)
                    send_telegram_message(bot_token, chat_id, "✅ Telegram успешно привязан к аккаунту!")
                else:
                    send_telegram_message(bot_token, chat_id, "❌ Неверный или использованный код привязки")
                return {'statusCode': 200, 'body': json.dumps({'ok': True})}
            
            response_text = (
                "👋 Привет! Я помогу создавать чеки для ЕкомКасса.\n\n"
                "Просто опиши покупку, например:\n• Кофе 200р\n• Консультация 5000₽\n• Аренда офиса 30000₽\n\n"
                "Я создам чек автоматически! ☕️"
            )
            send_telegram_message(bot_token, chat_id, response_text)
            return {'statusCode': 200, 'body': json.dumps({'ok': True})}
        
        handle_receipt_creation(text, chat_id, message['message_id'], user_id, bot_token)
        return {'statusCode': 200, 'body': json.dumps({'ok': True})}
        
    except Exception as e:
        print(f"[ERROR] Webhook handler failed: {e}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
