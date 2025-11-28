"""
Telegram bot webhook handler for EcomKassa receipt creation
Refactored with clear separation of concerns
"""
import json
import os
import urllib.request
import psycopg2
import psycopg2.extras
from typing import Dict, Any, List, Optional
from datetime import datetime


# ============================================================================
# CONFIGURATION
# ============================================================================

def get_bot_token() -> Optional[str]:
    """Get Telegram bot token from database"""
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
    """Get AI settings from database"""
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


def get_db_connection():
    """Get PostgreSQL database connection with schema prefix"""
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        raise ValueError("DATABASE_URL not configured")
    conn = psycopg2.connect(dsn)
    return conn


def execute_query(query: str, params=None, fetch_one=False, fetch_all=False, commit=False):
    """Execute query with automatic schema prefix handling"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Add schema prefix to table names - use simple full replacement
    schema = 't_p7891941_voice_ai_agent_1'
    tables_to_prefix = ['bot_settings', 'telegram_users', 'receipts', 'editing_previews', 
                        'chat_contexts', 'telegram_link_codes', 'ai_settings']
    modified_query = query
    
    for table in tables_to_prefix:
        # Only replace if schema prefix not already present
        if table in modified_query and f'{schema}.{table}' not in modified_query:
            # Replace all occurrences with schema prefix
            import re
            # Match table name with word boundaries
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


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def get_user_id_for_telegram(telegram_lookup_id: str) -> Optional[str]:
    """Get user_id by telegram lookup ID"""
    row = execute_query(
        "SELECT user_id FROM telegram_users WHERE telegram_lookup_id = %s",
        (telegram_lookup_id,),
        fetch_one=True
    )
    return row[0] if row else None


def save_receipt_to_db(user_id: str, receipt_data: Dict[str, Any], telegram_chat_id: int, telegram_message_id: int) -> int:
    """Save receipt to database and return receipt ID"""
    row = execute_query("""
        INSERT INTO receipts (user_id, items, total, payment_type, status, telegram_chat_id, telegram_message_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        user_id,
        psycopg2.extras.Json(receipt_data['items']),
        receipt_data['total'],
        receipt_data.get('payment_type', 'card'),
        'success',
        telegram_chat_id,
        telegram_message_id,
        datetime.now()
    ), fetch_one=True, commit=True)
    return row[0]


def get_receipt_by_uuid(uuid: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get receipt by short UUID prefix"""
    row = execute_query("""
        SELECT id, items, total, payment_type, status, telegram_chat_id, telegram_message_id, created_at
        FROM receipts 
        WHERE id::text LIKE %s AND user_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (f"{uuid}%", user_id), fetch_one=True)
    
    if not row:
        return None
    return {
        'id': row[0], 'items': row[1], 'total': row[2], 'payment_type': row[3],
        'status': row[4], 'telegram_chat_id': row[5], 'telegram_message_id': row[6], 'created_at': row[7]
    }


def get_last_receipt(user_id: str) -> Optional[Dict[str, Any]]:
    """Get last receipt for user"""
    row = execute_query("""
        SELECT id, items, total, payment_type, status, telegram_chat_id, telegram_message_id, created_at
        FROM receipts WHERE user_id = %s ORDER BY created_at DESC LIMIT 1
    """, (user_id,), fetch_one=True)
    
    if not row:
        return None
    return {
        'id': row[0], 'items': row[1], 'total': row[2], 'payment_type': row[3],
        'status': row[4], 'telegram_chat_id': row[5], 'telegram_message_id': row[6], 'created_at': row[7]
    }


def get_user_receipts_history(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get user receipts history"""
    rows = execute_query("""
        SELECT id, items, total, status, created_at
        FROM receipts WHERE user_id = %s ORDER BY created_at DESC LIMIT %s
    """, (user_id, limit), fetch_all=True)
    
    return [{'id': r[0], 'items': r[1], 'total': r[2], 'status': r[3], 'created_at': r[4]} for r in rows]


def save_editing_preview(chat_id: int, preview_data: Dict[str, Any], message_id: int, field_to_edit: str) -> None:
    """Save editing preview state"""
    execute_query("""
        INSERT INTO editing_previews (chat_id, preview_data, message_id, field_to_edit, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (chat_id) DO UPDATE SET preview_data = EXCLUDED.preview_data,
            message_id = EXCLUDED.message_id, field_to_edit = EXCLUDED.field_to_edit, created_at = EXCLUDED.created_at
    """, (chat_id, psycopg2.extras.Json(preview_data), message_id, field_to_edit, datetime.now()), commit=True)


def find_editing_preview_for_chat(chat_id: int) -> Optional[Dict[str, Any]]:
    """Find active editing preview for chat"""
    row = execute_query("""
        SELECT preview_data, message_id, field_to_edit
        FROM editing_previews WHERE chat_id = %s ORDER BY created_at DESC LIMIT 1
    """, (chat_id,), fetch_one=True)
    
    if not row:
        return None
    return {'preview_data': row[0], 'message_id': row[1], 'field_to_edit': row[2]}


def clear_editing_preview(chat_id: int) -> None:
    """Clear editing preview state"""
    execute_query("DELETE FROM editing_previews WHERE chat_id = %s", (chat_id,), commit=True)


def save_context_for_chat(chat_id: int, context_data: Dict[str, Any]) -> None:
    """Save conversation context"""
    execute_query("""
        INSERT INTO chat_contexts (chat_id, context_data, updated_at)
        VALUES (%s, %s, %s) ON CONFLICT (chat_id)
        DO UPDATE SET context_data = EXCLUDED.context_data, updated_at = EXCLUDED.updated_at
    """, (chat_id, psycopg2.extras.Json(context_data), datetime.now()), commit=True)


def get_context_for_chat(chat_id: int) -> Optional[Dict[str, Any]]:
    """Get conversation context"""
    row = execute_query("SELECT context_data FROM chat_contexts WHERE chat_id = %s", (chat_id,), fetch_one=True)
    return row[0] if row else None


def clear_context_for_chat(chat_id: int) -> None:
    """Clear conversation context"""
    execute_query("DELETE FROM chat_contexts WHERE chat_id = %s", (chat_id,), commit=True)


# ============================================================================
# TELEGRAM API
# ============================================================================

def send_telegram_message(bot_token: str, chat_id: int, text: str) -> None:
    """Send text message to Telegram chat"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = json.dumps({'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as response:
        response.read()


def send_telegram_message_with_buttons(bot_token: str, chat_id: int, text: str, buttons: List[List[Dict[str, str]]]) -> None:
    """Send message with inline keyboard buttons"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = json.dumps({
        'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML',
        'reply_markup': {'inline_keyboard': buttons}
    }).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as response:
        response.read()


def edit_telegram_message(bot_token: str, chat_id: int, message_id: int, text: str, buttons: Optional[List[List[Dict[str, str]]]] = None) -> None:
    """Edit existing message"""
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
    """Download file from Telegram servers"""
    get_file_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
    with urllib.request.urlopen(get_file_url) as response:
        file_info = json.loads(response.read().decode('utf-8'))
    file_path = file_info['result']['file_path']
    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    with urllib.request.urlopen(download_url) as response:
        return response.read()


# ============================================================================
# AI OPERATIONS
# ============================================================================

def parse_receipt_with_ai(text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Parse receipt using GPTunnel API"""
    ai_settings = get_ai_settings()
    if not ai_settings or not ai_settings.get('gptunnel_key'):
        raise ValueError("GPTunnel API key not configured")
    
    system_prompt = """Ты ассистент для создания чеков. Извлекай из текста:
1. Товары/услуги (name, price, quantity)
2. Способ оплаты (card/cash/default: card)

Формат ответа JSON:
{"items": [{"name": "...", "price": 100, "quantity": 1}], "payment_type": "card"}

Правила:
- Если количество не указано, ставь quantity: 1
- Округляй цены до копеек
- payment_type только "card" или "cash"
- Если способ оплаты не указан, используй "card"
"""
    
    user_message = text
    if context:
        user_message = f"Контекст:\n{json.dumps(context, ensure_ascii=False)}\n\nСообщение:\n{text}"
    
    url = "https://gptunnel.ru/v1/chat/completions"
    data = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
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
    parsed_data['total'] = round(sum(item['price'] * item.get('quantity', 1) for item in parsed_data['items']), 2)
    
    return parsed_data


def transcribe_voice_with_yandex(audio_bytes: bytes) -> str:
    """Transcribe voice using Yandex SpeechKit"""
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


# ============================================================================
# RECEIPT FORMATTING
# ============================================================================

def format_receipt_message(receipt_data: Dict[str, Any], receipt_id: int) -> str:
    """Format receipt for display"""
    items_text = []
    for item in receipt_data['items']:
        name, price, qty = item['name'], item['price'], item.get('quantity', 1)
        total = price * qty
        items_text.append(f"  • {name} — {price}₽ × {qty} = {total}₽" if qty > 1 else f"  • {name} — {price}₽")
    
    payment_emoji = "💳" if receipt_data.get('payment_type') == 'card' else "💵"
    payment_text = "Карта" if receipt_data.get('payment_type') == 'card' else "Наличные"
    short_uuid = str(receipt_id)[:8]
    
    return (f"🧾 <b>Чек #{short_uuid}</b>\n\n<b>Позиции:</b>\n" + "\n".join(items_text) +
            f"\n\n<b>Итого:</b> {receipt_data['total']}₽\n{payment_emoji} <b>Оплата:</b> {payment_text}\n\n✅ Чек создан!")


def create_receipt_buttons(receipt_id: int) -> List[List[Dict[str, str]]]:
    """Create action buttons for receipt"""
    return [
        [{"text": "🔄 Повторить", "callback_data": f"repeat_receipt_{receipt_id}"},
         {"text": "✏️ Изменить название", "callback_data": f"edit_name_{receipt_id}"}],
        [{"text": "💰 Изменить цену", "callback_data": f"edit_price_{receipt_id}"},
         {"text": "💳 Способ оплаты", "callback_data": f"edit_payment_{receipt_id}"}]
    ]


def create_payment_type_buttons(receipt_id: int) -> List[List[Dict[str, str]]]:
    """Create payment type selection buttons"""
    return [
        [{"text": "💳 Карта", "callback_data": f"payment_card_{receipt_id}"},
         {"text": "💵 Наличные", "callback_data": f"payment_cash_{receipt_id}"}],
        [{"text": "❌ Отмена", "callback_data": "cancel_edit"}]
    ]


# ============================================================================
# BUSINESS LOGIC HANDLERS
# ============================================================================

def handle_voice_message(message: Dict[str, Any], bot_token: str) -> Dict[str, Any]:
    """Handle voice message transcription"""
    try:
        voice = message['voice']
        file_id = voice['file_id']
        audio_data = download_telegram_file(bot_token, file_id)
        transcribed_text = transcribe_voice_with_yandex(audio_data)
        return {'text': transcribed_text}
    except Exception as e:
        print(f"[ERROR] Voice transcription failed: {e}")
        return {'error': str(e)}


def handle_receipt_creation(text: str, chat_id: int, message_id: int, user_id: str, bot_token: str) -> None:
    """Handle receipt creation from text"""
    context = get_context_for_chat(chat_id)
    print(f"[INFO] Creating receipt for chat {chat_id}, text: {text[:50]}...")
    
    try:
        receipt_data = parse_receipt_with_ai(text, context)
        print(f"[INFO] AI parsed receipt: {receipt_data}")
        
        if not receipt_data.get('items'):
            send_telegram_message(bot_token, chat_id, "❌ Не могу распознать товары в сообщении. Попробуй описать покупку по-другому или напиши 'отмена'")
            clear_context_for_chat(chat_id)
            return
        
        receipt_id = save_receipt_to_db(user_id, receipt_data, chat_id, message_id)
        message_text = format_receipt_message(receipt_data, receipt_id)
        buttons = create_receipt_buttons(receipt_id)
        
        send_telegram_message_with_buttons(bot_token, chat_id, message_text, buttons)
        save_context_for_chat(chat_id, {'last_receipt': receipt_data, 'last_message': text})
        print(f"[INFO] Receipt {receipt_id} created successfully")
        
    except Exception as e:
        print(f"[ERROR] Receipt creation failed: {e}")
        send_telegram_message(bot_token, chat_id, f"❌ Ошибка создания чека: {str(e)}. Попробуй ещё раз или напиши 'отмена'")
        clear_context_for_chat(chat_id)
        clear_editing_preview(chat_id)


def handle_repeat_receipt(receipt_id: int, chat_id: int, user_id: str, bot_token: str) -> None:
    """Handle receipt repeat"""
    receipt_data = get_receipt_by_uuid(str(receipt_id)[:8], user_id)
    
    if not receipt_data:
        send_telegram_message(bot_token, chat_id, "❌ Чек не найден")
        return
    
    new_receipt_id = save_receipt_to_db(user_id, receipt_data, chat_id, 0)
    message_text = format_receipt_message(receipt_data, new_receipt_id)
    buttons = create_receipt_buttons(new_receipt_id)
    send_telegram_message_with_buttons(bot_token, chat_id, message_text, buttons)


def handle_edit_field(receipt_id: int, field: str, chat_id: int, message_id: int, user_id: str, bot_token: str) -> None:
    """Handle field edit request"""
    receipt_data = get_receipt_by_uuid(str(receipt_id)[:8], user_id)
    
    if not receipt_data:
        send_telegram_message(bot_token, chat_id, "❌ Чек не найден")
        return
    
    save_editing_preview(chat_id, receipt_data, message_id, field)
    field_names = {'name': 'название товара', 'price': 'цену', 'payment': 'способ оплаты'}
    
    if field == 'payment':
        buttons = create_payment_type_buttons(receipt_id)
        edit_telegram_message(bot_token, chat_id, message_id, "💳 Выбери способ оплаты:", buttons)
    else:
        edit_telegram_message(bot_token, chat_id, message_id,
                            f"✏️ Отправь новое значение для: <b>{field_names.get(field, field)}</b>\n\nИли нажми /cancel для отмены")


def handle_edit_value(text: str, chat_id: int, message_id: int, user_id: str, bot_token: str) -> None:
    """Handle edit value input"""
    editing_preview = find_editing_preview_for_chat(chat_id)
    print(f"[INFO] Edit value for chat {chat_id}, text: {text}")
    
    if not editing_preview:
        print(f"[WARN] No editing preview found for chat {chat_id}")
        return
    
    preview_data = editing_preview['preview_data']
    field = editing_preview['field_to_edit']
    preview_message_id = editing_preview['message_id']
    
    try:
        if field == 'name' and preview_data.get('items'):
            preview_data['items'][0]['name'] = text
        elif field == 'price':
            new_price = float(text.replace(',', '.').replace('₽', '').strip())
            if preview_data.get('items'):
                preview_data['items'][0]['price'] = new_price
                preview_data['total'] = sum(item['price'] * item.get('quantity', 1) for item in preview_data['items'])
        
        new_receipt_id = save_receipt_to_db(user_id, preview_data, chat_id, message_id)
        message_text = format_receipt_message(preview_data, new_receipt_id)
        buttons = create_receipt_buttons(new_receipt_id)
        
        edit_telegram_message(bot_token, chat_id, preview_message_id, message_text, buttons)
        clear_editing_preview(chat_id)
        send_telegram_message(bot_token, chat_id, "✅ Чек обновлен!")
        print(f"[INFO] Receipt updated successfully")
        
    except ValueError:
        send_telegram_message(bot_token, chat_id, "❌ Неверный формат цены. Попробуй ещё раз или напиши 'отмена'")
    except Exception as e:
        print(f"[ERROR] Edit value failed: {e}")
        send_telegram_message(bot_token, chat_id, f"❌ Ошибка обновления: {str(e)}. Напиши 'отмена' чтобы начать заново")
        clear_editing_preview(chat_id)


def handle_payment_change(receipt_id: int, payment_type: str, chat_id: int, message_id: int, user_id: str, bot_token: str) -> None:
    """Handle payment type change"""
    receipt_data = get_receipt_by_uuid(str(receipt_id)[:8], user_id)
    
    if not receipt_data:
        send_telegram_message(bot_token, chat_id, "❌ Чек не найден")
        return
    
    receipt_data['payment_type'] = payment_type
    new_receipt_id = save_receipt_to_db(user_id, receipt_data, chat_id, message_id)
    message_text = format_receipt_message(receipt_data, new_receipt_id)
    buttons = create_receipt_buttons(new_receipt_id)
    
    edit_telegram_message(bot_token, chat_id, message_id, message_text, buttons)
    clear_editing_preview(chat_id)


def handle_callback_query(callback_query: Dict[str, Any], bot_token: str) -> Dict[str, Any]:
    """Handle callback query from inline buttons"""
    callback_data = callback_query.get('data', '')
    message = callback_query['message']
    chat_id, message_id = message['chat']['id'], message['message_id']
    user_id_from_callback = callback_query['from']['id']
    
    lookup_id = f"telegram_{user_id_from_callback}"
    user_id = get_user_id_for_telegram(lookup_id)
    
    if not user_id:
        send_telegram_message(bot_token, chat_id, "❌ Пользователь не найден. Отправь /start")
        return create_response({'ok': True})
    
    if callback_data.startswith('repeat_receipt_'):
        receipt_id = int(callback_data.replace('repeat_receipt_', ''))
        handle_repeat_receipt(receipt_id, chat_id, user_id, bot_token)
    elif callback_data.startswith('edit_name_'):
        receipt_id = int(callback_data.replace('edit_name_', ''))
        handle_edit_field(receipt_id, 'name', chat_id, message_id, user_id, bot_token)
    elif callback_data.startswith('edit_price_'):
        receipt_id = int(callback_data.replace('edit_price_', ''))
        handle_edit_field(receipt_id, 'price', chat_id, message_id, user_id, bot_token)
    elif callback_data.startswith('edit_payment_'):
        receipt_id = int(callback_data.replace('edit_payment_', ''))
        handle_edit_field(receipt_id, 'payment', chat_id, message_id, user_id, bot_token)
    elif callback_data.startswith('payment_card_'):
        receipt_id = int(callback_data.replace('payment_card_', ''))
        handle_payment_change(receipt_id, 'card', chat_id, message_id, user_id, bot_token)
    elif callback_data.startswith('payment_cash_'):
        receipt_id = int(callback_data.replace('payment_cash_', ''))
        handle_payment_change(receipt_id, 'cash', chat_id, message_id, user_id, bot_token)
    elif callback_data == 'cancel_edit':
        clear_editing_preview(chat_id)
        edit_telegram_message(bot_token, chat_id, message_id, "❌ Редактирование отменено")
    
    return create_response({'ok': True})


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

def handle_start_command(text: str, chat_id: int, bot_token: str, lookup_id: str) -> None:
    """Handle /start command"""
    link_code = text.replace('/start', '').strip()
    
    if link_code and link_code.startswith('LINK-'):
        row = execute_query("SELECT user_id FROM telegram_link_codes WHERE code = %s AND used = false", (link_code,), fetch_one=True)
        
        if row:
            user_id = row[0]
            execute_query("INSERT INTO telegram_users (telegram_lookup_id, user_id) VALUES (%s, %s) ON CONFLICT (telegram_lookup_id) DO UPDATE SET user_id = EXCLUDED.user_id", (lookup_id, user_id), commit=True)
            execute_query("UPDATE telegram_link_codes SET used = true WHERE code = %s", (link_code,), commit=True)
            send_telegram_message(bot_token, chat_id, "✅ Telegram успешно привязан к аккаунту!")
        else:
            send_telegram_message(bot_token, chat_id, "❌ Неверный или использованный код привязки")
        return
    
    response_text = (
        "👋 Привет! Я помогу создавать чеки для ЕкомКасса.\n\n"
        "Просто опиши покупку, например:\n• Кофе 200р\n• Продал телефон за 15000\n• Аренда офиса 30000 наличными\n\n"
        "💡 Команда /repeat повторит последний чек\n\nЯ создам чек автоматически! ☕️"
    )
    send_telegram_message(bot_token, chat_id, response_text)


def handle_help_command(chat_id: int, bot_token: str) -> None:
    """Handle /help command"""
    response_text = (
        "📝 <b>Как пользоваться:</b>\n\n1. Опиши товар/услугу и сумму\n2. Я создам чек автоматически\n3. Чек отправится в ЕкомКасса\n\n"
        "<b>Примеры:</b>\n• Кофе латте 250р\n• Консультация 5000\n• 3 пирожка по 50р\n\n"
        "<b>Команды:</b>\n/repeat - Повторить последний чек\n/history - История чеков\n/help - Эта справка"
    )
    send_telegram_message(bot_token, chat_id, response_text)


def handle_history_command(chat_id: int, user_id: str, bot_token: str) -> None:
    """Handle /history command"""
    history = get_user_receipts_history(user_id, limit=10)
    
    if not history:
        send_telegram_message(bot_token, chat_id, "📋 История чеков пуста")
        return
    
    response_text = "📋 <b>Последние 10 чеков:</b>\n\nВыбери чек для повтора:"
    history_buttons = []
    
    for receipt in history:
        created_at = receipt['created_at'].strftime('%d.%m %H:%M')
        status_emoji = '✅' if receipt['status'] == 'success' else '⚠️'
        items_text = ', '.join([item['name'] for item in receipt['items'][:2]])
        if len(receipt['items']) > 2:
            items_text += f" +{len(receipt['items']) - 2}"
        button_text = f"{status_emoji} {created_at} • {items_text[:25]} • {receipt['total']}₽"
        history_buttons.append([{"text": button_text, "callback_data": f"repeat_receipt_{receipt['id']}"}])
    
    send_telegram_message_with_buttons(bot_token, chat_id, response_text, history_buttons)


def handle_repeat_command(text: str, chat_id: int, user_id: str, bot_token: str) -> None:
    """Handle /repeat command"""
    parts = text.split()
    
    if len(parts) == 2 and parts[1].isdigit():
        uuid_to_find = parts[1]
        receipt_data = get_receipt_by_uuid(uuid_to_find, user_id)
        
        if not receipt_data:
            send_telegram_message(bot_token, chat_id, f"❌ Чек #{uuid_to_find} не найден")
            return
        
        handle_repeat_receipt(receipt_data['id'], chat_id, user_id, bot_token)
    else:
        last_receipt = get_last_receipt(user_id)
        
        if not last_receipt:
            send_telegram_message(bot_token, chat_id, "❌ Нет сохраненных чеков")
            return
        
        handle_repeat_receipt(last_receipt['id'], chat_id, user_id, bot_token)


# ============================================================================
# MAIN WEBHOOK HANDLER
# ============================================================================

def create_response(data: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    """Create HTTP response"""
    return {'statusCode': status_code, 'headers': {'Content-Type': 'application/json'}, 'body': json.dumps(data)}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Telegram webhook для создания чеков через бота
    Args: event - dict с httpMethod, body от Telegram
          context - объект с request_id, function_name
    Returns: HTTP response dict
    '''
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
    
    # GET endpoint to setup webhook
    if method == 'GET':
        bot_token = get_bot_token()
        if not bot_token:
            return create_response({'error': 'Bot token not configured'}, 500)
        
        webhook_url = 'https://functions.poehali.dev/c931c0bd-bad6-4f16-9a76-f67296c311b1'
        telegram_api_url = f'https://api.telegram.org/bot{bot_token}/setWebhook?url={webhook_url}'
        
        try:
            req = urllib.request.Request(telegram_api_url, method='POST')
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())
                return create_response({'success': True, 'webhook_set': result}, 200)
        except Exception as e:
            return create_response({'error': f'Failed to set webhook: {str(e)}'}, 500)
    
    if method != 'POST':
        return create_response({'error': 'Method not allowed'}, 405)
    
    bot_token = get_bot_token()
    if not bot_token:
        return create_response({'error': 'Bot token not configured'}, 500)
    
    try:
        update = json.loads(event.get('body', '{}'))
        print(f"[INFO] Received update: {json.dumps(update)[:200]}")
        
        if 'callback_query' in update:
            print(f"[INFO] Processing callback query")
            return handle_callback_query(update['callback_query'], bot_token)
        
        if 'message' not in update:
            print(f"[INFO] No message in update, ignoring")
            return create_response({'ok': True})
        
        message = update['message']
        chat_id = message['chat']['id']
        chat_type = message['chat'].get('type', 'private')
        sender_id = message.get('from', {}).get('id', chat_id)
        
        # Determine lookup_id and check editing state
        text = ''
        editing_preview_id = None
        
        if chat_type in ['group', 'supergroup']:
            lookup_id = f"telegram_{sender_id}"
            editing_preview_id = find_editing_preview_for_chat(sender_id)
            
            if editing_preview_id:
                text = message.get('text', '')
                print(f"[INFO] Group message in editing mode, sender {sender_id}, text: {text}")
            else:
                text_raw = message.get('text', '')
                bot_mentioned = '@ecomkassa_ai_bot' in text_raw.lower() or message.get('reply_to_message', {}).get('from', {}).get('is_bot', False)
                print(f"[INFO] Group message, sender {sender_id}, mentioned: {bot_mentioned}, text: {text_raw[:50] if text_raw else 'empty'}")
                if not bot_mentioned:
                    return create_response({'ok': True})
                text = text_raw.replace('@ecomkassa_ai_bot', '').replace('@Ecomkassa_ai_bot', '').strip()
        else:
            lookup_id = f"telegram_{chat_id}"
            text = message.get('text', '')
            editing_preview_id = find_editing_preview_for_chat(chat_id)
        
        # Handle voice messages
        if 'voice' in message:
            send_telegram_message(bot_token, chat_id, "🎤 Распознаю голос...")
            voice_result = handle_voice_message(message, bot_token)
            if voice_result.get('error'):
                send_telegram_message(bot_token, chat_id, f"❌ Ошибка: {voice_result['error']}")
                return create_response({'ok': True})
            text = voice_result['text']
            send_telegram_message(bot_token, chat_id, f"✅ Распознано: \"{text}\"\n\nОбрабатываю...")
        
        user_id = get_user_id_for_telegram(lookup_id)
        if not user_id:
            print(f"[WARN] User not found for lookup_id: {lookup_id}")
            send_telegram_message(bot_token, chat_id, "❌ Пользователь не найден. Отправь /start с кодом привязки")
            return create_response({'ok': True})
        
        print(f"[INFO] Processing message from user {user_id}, chat {chat_id}, text: {text[:50]}...")
        
        # Clear context on cancel command
        if text.lower() in ['отмена', 'отменить', 'cancel']:
            clear_context_for_chat(chat_id)
            clear_editing_preview(chat_id)
            send_telegram_message(bot_token, chat_id, "✅ Контекст очищен. Можешь начать заново")
            return create_response({'ok': True})
        
        # Handle commands
        if text.startswith('/start'):
            handle_start_command(text, chat_id, bot_token, lookup_id)
            return create_response({'ok': True})
        if text.startswith('/help'):
            handle_help_command(chat_id, bot_token)
            return create_response({'ok': True})
        if text.startswith('/history') or text.lower().strip() == 'история':
            handle_history_command(chat_id, user_id, bot_token)
            return create_response({'ok': True})
        if text.startswith('/repeat') or text.lower().strip() == 'повтори':
            handle_repeat_command(text, chat_id, user_id, bot_token)
            return create_response({'ok': True})
        
        # Handle editing state
        if editing_preview_id:
            handle_edit_value(text, chat_id, message['message_id'], user_id, bot_token)
            return create_response({'ok': True})
        
        # Default: create receipt
        handle_receipt_creation(text, chat_id, message['message_id'], user_id, bot_token)
        return create_response({'ok': True})
        
    except Exception as e:
        print(f"[ERROR] Webhook handler failed: {e}")
        return create_response({'error': str(e)}, 500)