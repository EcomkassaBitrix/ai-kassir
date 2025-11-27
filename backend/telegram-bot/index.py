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
        
        # Handle voice messages
        if 'voice' in message:
            # Send processing notification
            send_telegram_message(bot_token, chat_id, "🎤 Распознаю голос...")
            
            voice_result = handle_voice_message(message, bot_token)
            if voice_result.get('error'):
                send_telegram_message(bot_token, chat_id, f"❌ Ошибка: {voice_result['error']}")
                return create_response({'ok': True})
            text = voice_result.get('text', '')
            print(f"[DEBUG] Voice transcribed: {text}")
            
            # Show transcribed text to user
            send_telegram_message(bot_token, chat_id, f"✅ Распознано: \"{text}\"\n\nОбрабатываю...")
        else:
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
                "💡 Команда /repeat повторит последний чек\n\n"
                "Я создам чек автоматически! ☕️"
            )
            send_telegram_message(bot_token, chat_id, response_text)
            return create_response({'ok': True})
        
        if text.startswith('/help'):
            response_text = (
                "📝 <b>Как пользоваться:</b>\n\n"
                "1. Опиши товар/услугу и сумму\n"
                "2. Я создам чек автоматически\n"
                "3. Чек отправится в ЕкомКасса\n\n"
                "<b>Примеры:</b>\n"
                "• Кофе латте 250р\n"
                "• Консультация 5000\n"
                "• 3 пирожка по 50р\n\n"
                "<b>Команды:</b>\n"
                "/repeat - Повторить последний чек\n"
                "/history - История чеков\n"
                "/help - Эта справка"
            )
            send_telegram_message(bot_token, chat_id, response_text)
            return create_response({'ok': True})
        
        if text.startswith('/history') or text.lower().strip() == 'история':
            user_id = get_user_id_for_telegram(chat_id)
            history = get_user_receipts_history(user_id, limit=10)
            
            if not history:
                send_telegram_message(bot_token, chat_id, "📋 История чеков пуста")
                return create_response({'ok': True})
            
            response_text = "📋 <b>Последние 10 чеков:</b>\n\nВыбери чек для повтора:"
            
            # Create buttons for each receipt
            history_buttons = []
            for idx, receipt in enumerate(history):
                created_at = receipt['created_at'].strftime('%d.%m %H:%M')
                status_emoji = '✅' if receipt['status'] == 'success' else '⚠️'
                total = receipt['total']
                receipt_id = receipt['id']
                
                items_text = ', '.join([item['name'] for item in receipt['items'][:2]])
                if len(receipt['items']) > 2:
                    items_text += f" +{len(receipt['items']) - 2}"
                
                button_text = f"{status_emoji} {created_at} • {items_text[:25]} • {total}₽"
                history_buttons.append([{
                    "text": button_text,
                    "callback_data": f"repeat_receipt_{receipt_id}"
                }])
            
            send_telegram_message_with_buttons(bot_token, chat_id, response_text, history_buttons)
            return create_response({'ok': True})
        
        # Check for "повтори UUID" pattern
        if text.lower().startswith('повтори '):
            parts = text.split()
            if len(parts) == 2 and parts[1].isdigit():
                # User wants to repeat specific receipt by UUID
                uuid_to_find = parts[1]
                user_id = get_user_id_for_telegram(chat_id)
                
                print(f"[DEBUG] Repeat by UUID: {uuid_to_find}, user_id: {user_id}, chat_id: {chat_id}")
                
                # Find receipt by UUID
                receipt_data = get_receipt_by_uuid(uuid_to_find, user_id)
                
                if not receipt_data:
                    print(f"[ERROR] Receipt not found: UUID={uuid_to_find}, user_id={user_id}")
                    send_telegram_message(bot_token, chat_id, f"❌ Чек с UUID {uuid_to_find} не найден")
                    return create_response({'ok': True})
                
                print(f"[DEBUG] Receipt found! Data: {receipt_data}")
                
                # Generate new preview_id
                import uuid
                preview_id = str(uuid.uuid4())
                
                print(f"[DEBUG] Generated preview_id: {preview_id}")
                
                # Store preview data
                preview_data = {
                    'receipt_data': receipt_data,
                    'user_id': user_id,
                    'user_message': f"Повтор чека UUID {uuid_to_find}"
                }
                
                print(f"[DEBUG] Storing preview data...")
                store_preview_data(preview_id, preview_data, chat_id)
                
                print(f"[DEBUG] Showing receipt preview...")
                show_receipt_preview(bot_token, chat_id, preview_data, preview_id)
                
                print(f"[DEBUG] Repeat by UUID completed successfully")
                return create_response({'ok': True})
        
        if text.startswith('/repeat') or text.lower().strip() in ['повтори', 'повтори последний', 'повтори запрос', 'повторить']:
            user_id = get_user_id_for_telegram(chat_id)
            last_request = get_last_successful_request(chat_id)
            
            if not last_request:
                send_telegram_message(bot_token, chat_id, "❌ Нет предыдущих успешных запросов для повтора")
                return create_response({'ok': True})
            
            # Show preview with same data as last time
            preview_id = last_request['preview_id']
            preview_data = last_request['preview_data']
            
            # Store preview data for confirmation
            store_preview_data(preview_id, preview_data, chat_id)
            
            # Show preview message
            show_receipt_preview(bot_token, chat_id, preview_data, preview_id)
            return create_response({'ok': True})
        
        user_id = get_user_id_for_telegram(chat_id)
        print(f"[DEBUG] chat_id={chat_id}, resolved user_id='{user_id}'")
        
        # Check if user is editing a field
        editing_preview_id = find_editing_preview_for_chat(chat_id)
        print(f"[DEBUG] find_editing_preview_for_chat returned: {editing_preview_id}")
        if editing_preview_id:
            editing_field = get_editing_state(editing_preview_id)
            print(f"[DEBUG] User is editing field: {editing_field}")
            
            if editing_field:
                # Process the new value
                preview_data = get_preview_data(editing_preview_id)
                print(f"[DEBUG] preview_data exists: {preview_data is not None}")
                if preview_data:
                    # Update preview with new value
                    update_success = update_preview_field(editing_preview_id, editing_field, text, user_id)
                    
                    if update_success:
                        delete_editing_state(editing_preview_id)
                        send_telegram_message(bot_token, chat_id, "✅ Изменения сохранены!\n\nВозвращаю к чеку...")
                        
                        # Show updated preview
                        import time
                        time.sleep(1)
                        
                        # Regenerate and show preview
                        show_updated_preview(bot_token, chat_id, editing_preview_id, user_id)
                        return create_response({'ok': True})
                    else:
                        delete_editing_state(editing_preview_id)
                        send_telegram_message(bot_token, chat_id, "❌ Ошибка при сохранении. Попробуй снова.")
                        return create_response({'ok': True})
        
        # Get preview of the receipt
        preview_result = process_receipt_ai(text, user_id, preview_only=True)
        print(f"[DEBUG] preview_result: {preview_result.get('success')}, preview: {preview_result.get('preview')}")
        
        # Clean up any old editing states for this chat when creating new preview
        old_preview_id = find_editing_preview_for_chat(chat_id)
        if old_preview_id:
            delete_editing_state(old_preview_id)
            delete_preview_data(old_preview_id)
        
        if preview_result.get('preview'):
            receipt_data = preview_result.get('receipt', {})
            items = receipt_data.get('items', [])
            total = receipt_data.get('total', 0)
            payments = receipt_data.get('payments', [])
            client_data = receipt_data.get('client', {})
            operation_type = preview_result.get('operation_type', 'sell')
            document_type = preview_result.get('document_type', 'receipt')  # CRITICAL: Get document type from backend
            
            # Operation type names
            operation_names = {
                'sell': '🛒 Приход (продажа)',
                'refund': '↩️ Возврат прихода',
                'sell_correction': '📝 Коррекция прихода',
                'refund_correction': '📝 Коррекция расхода'
            }
            
            # CRITICAL: Detect document type from backend response OR receipt_data
            payment_link_enabled = receipt_data.get('payment_link_enabled', False)
            is_payment_link = (document_type == 'link') or payment_link_enabled
            document_type_text = "🔗 Платежная ссылка" if is_payment_link else "🧾 Чек"
            
            print(f"[DEBUG] document_type={document_type}, payment_link_enabled={payment_link_enabled}, is_payment_link={is_payment_link}")
            
            response_text = "📋 <b>Проверь перед отправкой:</b>\n\n"
            
            # Document type with provider on same line for payment links
            if is_payment_link:
                provider_name = receipt_data.get('payment_provider_name', 'Не выбран')
                response_text += f"<b>Тип документа:</b> 🔗 Платежная ссылка Провайдер: {provider_name}\n"
            else:
                response_text += f"<b>Тип документа:</b> {document_type_text}\n"
            
            # Remove emojis from operation names
            operation_names_clean = {
                'sell': 'Приход',
                'refund': 'Возврат прихода',
                'sell_correction': 'Коррекция прихода',
                'refund_correction': 'Коррекция расхода'
            }
            
            response_text += f"<b>Тип операции:</b> {operation_names_clean.get(operation_type, operation_type)}\n\n"
            
            # Company info (SNO and payment address) IMMEDIATELY after operation type
            company_data = receipt_data.get('company', {})
            sno = company_data.get('sno', 'usn_income')
            payment_address = company_data.get('payment_address', '')
            
            sno_names = {
                'usn_income': 'УСН доход',
                'usn_income_outcome': 'УСН доход-расход',
                'osn': 'ОСНО',
                'esn': 'ЕСХН',
                'patent': 'Патент'
            }
            
            response_text += f"<b>💼 СНО:</b> {sno_names.get(sno, sno)}\n"
            if payment_address:
                response_text += f"<b>📍 Адрес расчетов:</b> {payment_address}\n"
            
            response_text += f"<b>📧 Email клиента:</b> {client_data.get('email', 'Не указан')}\n"
            
            # Items with all details
            response_text += "\n<b>Товары/Услуги:</b>\n"
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
            
            # Payment method - same as show_receipt_preview
            if is_payment_link:
                response_text += f"<b>Способ оплаты:</b> 💳 Безналичный\n"
            elif payments and len(payments) > 1:
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
            
            # Add operation_type to receipt_data
            receipt_data['operation_type'] = operation_type
            
            # Save preview data to send with callback
            preview_id = save_preview_data(chat_id, text, user_id, receipt_data)
            
            # Send with inline keyboard
            send_telegram_message_with_buttons(
                bot_token, 
                chat_id, 
                response_text,
                [
                    [{"text": "✅ Отправить запрос", "callback_data": f"confirm_{preview_id}"}],
                    [{"text": "✏️ Изменить", "callback_data": f"edit_{preview_id}"}],
                    [{"text": "❌ Отменить", "callback_data": f"cancel_{preview_id}"}]
                ]
            )
            
        else:
            # Clean up any old editing states for this chat
            old_preview_id = find_editing_preview_for_chat(chat_id)
            if old_preview_id:
                delete_editing_state(old_preview_id)
                delete_preview_data(old_preview_id)
            
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


def send_photo(bot_token: str, chat_id: int, photo_url: str, caption: str = '') -> None:
    '''Send photo by URL to Telegram chat'''
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    data = {
        'chat_id': chat_id,
        'photo': photo_url,
        'caption': caption,
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
        print(f"[ERROR] Failed to send photo: {e}")


def process_receipt_ai(user_message: str, user_id: str, preview_only: bool = False) -> Dict[str, Any]:
    process_receipt_url = 'https://functions.poehali.dev/734da785-2867-4c5d-b20c-90fc6d86b11c'
    
    # CRITICAL: Auto-detect document type from keywords
    # Keywords for payment link: ссылка, платеж, QR, эквайринг, СБП
    # Default: чек (receipt)
    message_lower = user_message.lower()
    link_keywords = ['ссылк', 'платеж', 'qr', 'эквайринг', 'сбп', 'оплат']  # Partial match
    document_type = 'link' if any(kw in message_lower for kw in link_keywords) else 'receipt'
    
    print(f"[DEBUG] Auto-detected document_type: {document_type} from message: {user_message[:50]}...")
    
    # CRITICAL: Auto-detect payment provider from keywords
    # Provider keywords mapping (partial match, case-insensitive)
    provider_keywords = {
        'сбербанк': ['сбербанк', 'sberbank', 'сбер'],
        'юкасса': ['юкасса', 'юкасс', 'yookassa', 'юкаса'],
        'тинькофф': ['тинькофф', 'тиньков', 'tinkoff', 'tcs'],
        'альфа': ['альфа', 'alfa', 'альфабанк'],
        'втб': ['втб', 'vtb'],
        'райффайзен': ['райффайзен', 'raiffeisen'],
        'газпромбанк': ['газпром', 'gazprom'],
        'россельхозбанк': ['россельхоз', 'рсхб'],
        'открытие': ['открытие', 'otkritie'],
        'промсвязьбанк': ['промсвязь', 'psb']
    }
    
    detected_provider_name = None
    for provider_name, keywords in provider_keywords.items():
        if any(kw in message_lower for kw in keywords):
            detected_provider_name = provider_name
            print(f"[DEBUG] Auto-detected payment provider: {provider_name}")
            break
    
    # CRITICAL: If provider detected, force document_type to 'link'
    if detected_provider_name:
        document_type = 'link'
        print(f"[DEBUG] Provider detected - forcing document_type to 'link'")
    
    # If provider detected, load user's providers and match
    auto_selected_provider = None
    if detected_provider_name:
        user_providers = get_payment_providers(user_id)
        if user_providers:
            # Match detected provider name with user's available providers
            for provider in user_providers:
                provider_desc = provider.get('description', '').lower()
                provider_id = provider.get('id')
                
                # Check if any keyword matches the provider description
                for keyword in provider_keywords.get(detected_provider_name, []):
                    if keyword in provider_desc:
                        auto_selected_provider = {
                            'id': provider_id,
                            'name': provider.get('description', f'Провайдер {provider_id}'),
                            'detected_keyword': detected_provider_name
                        }
                        print(f"[DEBUG] Matched provider: id={provider_id}, name={auto_selected_provider['name']}")
                        break
                
                if auto_selected_provider:
                    break
            
            # If provider keyword found but not available for user
            if not auto_selected_provider:
                print(f"[WARN] Provider '{detected_provider_name}' requested but not available for user {user_id}")
        else:
            print(f"[WARN] Could not load providers for user {user_id}")
    
    print(f"[DEBUG] auto_selected_provider: {auto_selected_provider}")
    
    payload = {
        'message': user_message,
        'operation_type': 'Приход',
        'preview_only': preview_only,
        'external_id': f"TG_{int(datetime.now().timestamp())}",
        'document_type': document_type,  # CRITICAL: Pass document type to backend
        'auto_selected_provider': auto_selected_provider,  # CRITICAL: Auto-selected payment provider
        'detected_provider_keyword': detected_provider_name,  # CRITICAL: Keyword that was detected (even if not available)
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


def process_receipt_ai_with_edited_data(receipt_data: dict, user_id: str) -> Dict[str, Any]:
    '''Send edited receipt data directly to process-receipt backend'''
    process_receipt_url = 'https://functions.poehali.dev/734da785-2867-4c5d-b20c-90fc6d86b11c'
    
    # Extract operation_type from receipt_data or default to 'sell'
    operation_type = receipt_data.get('operation_type', 'sell')
    
    # CRITICAL: Detect document type from payment_link_enabled flag
    document_type = 'link' if receipt_data.get('payment_link_enabled') else 'receipt'
    print(f"[DEBUG] Document type from receipt_data: {document_type}")
    
    payload = {
        'message': 'Edited receipt from Telegram',  # Dummy message, not used
        'operation_type': operation_type,
        'preview_only': False,  # Send to Ecomkassa
        'edited_data': receipt_data,  # CRITICAL: Pass edited receipt directly
        'document_type': document_type,  # CRITICAL: Pass document type
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


def get_db_connection():
    '''
    Get PostgreSQL database connection
    Returns: psycopg2 connection or None
    '''
    try:
        dsn = os.environ.get('DATABASE_URL')
        if not dsn:
            print("[ERROR] DATABASE_URL not set")
            return None
        return psycopg2.connect(dsn)
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return None


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
    
    # CRITICAL DEBUG: Log ALL incoming callback_data
    print(f"[DEBUG] ====== CALLBACK RECEIVED ======")
    print(f"[DEBUG] callback_data: '{callback_data}'")
    print(f"[DEBUG] chat_id: {chat_id}, message_id: {message_id}")
    print(f"[DEBUG] ================================")
    
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
        receipt_data = preview_data.get('receipt_data')
        
        # CRITICAL: Use edited receipt_data if available, otherwise parse from text
        if receipt_data:
            print(f"[DEBUG] Using edited receipt_data from preview")
            # Send edited receipt directly to process-receipt with edited_data flag
            receipt_result = process_receipt_ai_with_edited_data(receipt_data, user_id)
        else:
            print(f"[DEBUG] No receipt_data in preview, parsing from text")
            # Fallback: parse from original message
            receipt_result = process_receipt_ai(user_message, user_id, preview_only=False)
        
        if receipt_result.get('success'):
            receipt_data = receipt_result.get('receipt', {})
            items = receipt_data.get('items', [])
            total = receipt_data.get('total', 0)
            payments = receipt_data.get('payments', [])
            
            payment_type = payments[0].get('type', '1') if payments else '1'
            payment_names = {'0': "💵 Наличные", '1': "💳 Карта", '2': "📝 Предоплата", '3': "🏦 Кредит"}
            payment_str = payment_names.get(str(payment_type), "💳 Безналичный")
            
            # CRITICAL: Check if this is a payment link receipt
            payment_link = receipt_result.get('payment_link', '')
            qr_code = receipt_result.get('qr_code', '')
            
            # Check if payment_link_enabled in receipt_data (edited data from preview)
            is_payment_link = bool(payment_link) or receipt_data.get('payment_link_enabled', False)
            
            if is_payment_link:
                response_text = "✅ Платежная ссылка создана!\n\n"
            else:
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
            
            # CRITICAL: Add payment link and QR code if present
            if payment_link:
                response_text += f"\n\n🔗 <b>Ссылка на оплату:</b>\n{payment_link}"
            
            edit_message(bot_token, chat_id, message_id, response_text)
            
            # CRITICAL: Send QR code as photo if available
            if qr_code:
                send_photo(bot_token, chat_id, qr_code, "📱 Отсканируй QR-код для оплаты")
            
            # CRITICAL: Save last successful request for /repeat command
            save_last_successful_request(chat_id, preview_id, preview_data)
        else:
            error_msg = receipt_result.get('message') or receipt_result.get('error', 'Не удалось создать чек')
            edit_message(bot_token, chat_id, message_id, f"❌ Ошибка: {error_msg}")
        
        delete_preview_data(preview_id)
    
    elif callback_data.startswith('repeat_receipt_'):
        # Repeat receipt from history
        receipt_id = int(callback_data.replace('repeat_receipt_', ''))
        user_id = get_user_id_for_telegram(chat_id)
        
        # Load receipt data from database
        receipt_data = get_receipt_by_id(receipt_id, user_id)
        
        if not receipt_data:
            edit_message(bot_token, chat_id, message_id, "❌ Чек не найден")
            return create_response({'ok': True})
        
        # Generate new preview_id
        import uuid
        preview_id = str(uuid.uuid4())
        
        # Store preview data
        preview_data = {
            'receipt_data': receipt_data,
            'user_id': user_id,
            'user_message': f"Повтор чека ID {receipt_id}"
        }
        
        store_preview_data(preview_id, preview_data, chat_id)
        
        # Show preview
        show_receipt_preview(bot_token, chat_id, preview_data, preview_id)
        return create_response({'ok': True})
        
    elif callback_data.startswith('cancel_'):
        preview_id = callback_data.replace('cancel_', '')
        edit_message(bot_token, chat_id, message_id, "❌ Создание чека отменено")
        delete_preview_data(preview_id)
    
    # CRITICAL: Check specific edit_* patterns BEFORE general edit_
    elif callback_data.startswith('edit_item_') or callback_data.startswith('edit_price_') or callback_data.startswith('edit_quantity_') or callback_data.startswith('edit_measure_') or callback_data.startswith('edit_vat_') or callback_data.startswith('edit_payment_object_') or callback_data.startswith('edit_payment_method_') or callback_data.startswith('edit_payment_type_') or callback_data.startswith('edit_payment_sum_') or callback_data.startswith('edit_sno_') or callback_data.startswith('edit_payment_address_') or callback_data.startswith('edit_operation_type_') or callback_data.startswith('edit_email_') or callback_data.startswith('edit_phone_'):
        # Extract field type and preview_id
        print(f"[DEBUG] Edit field button clicked! callback_data: {callback_data}")
        if callback_data.startswith('edit_item_'):
            field = 'item'
            preview_id = callback_data.replace('edit_item_', '')
            prompt_text = "📝 <b>Изменить товар/услугу</b>\n\nОтправь новое название товара или услуги текстом.\n\nНапример: <code>кофе латте</code>"
        elif callback_data.startswith('edit_price_'):
            field = 'price'
            preview_id = callback_data.replace('edit_price_', '')
            prompt_text = "💰 <b>Изменить цену</b>\n\nОтправь новую цену числом.\n\nНапример: <code>350</code>"
        elif callback_data.startswith('edit_quantity_'):
            field = 'quantity'
            preview_id = callback_data.replace('edit_quantity_', '')
            prompt_text = "📊 <b>Изменить количество</b>\n\nОтправь новое количество числом.\n\nНапример: <code>2</code>"
        elif callback_data.startswith('edit_measure_'):
            field = 'measure'
            preview_id = callback_data.replace('edit_measure_', '')
            prompt_text = "📏 <b>Выбери единицу измерения:</b>"
            
            measure_buttons = [
                [{"text": "шт", "callback_data": f"set_measure_шт_{preview_id}"}],
                [{"text": "кг", "callback_data": f"set_measure_кг_{preview_id}"}],
                [{"text": "л", "callback_data": f"set_measure_л_{preview_id}"}],
                [{"text": "м", "callback_data": f"set_measure_м_{preview_id}"}],
                [{"text": "услуга", "callback_data": f"set_measure_услуга_{preview_id}"}],
                [{"text": "« Назад", "callback_data": f"edit_group_items_{preview_id}"}]
            ]
            
            edit_message_with_buttons(bot_token, chat_id, message_id, prompt_text, measure_buttons)
            return create_response({'ok': True})
        elif callback_data.startswith('edit_vat_'):
            field = 'vat'
            preview_id = callback_data.replace('edit_vat_', '')
            prompt_text = "🧾 <b>Выбери ставку НДС:</b>"
            
            vat_buttons = [
                [{"text": "Без НДС", "callback_data": f"set_vat_none_{preview_id}"}],
                [{"text": "НДС 0%", "callback_data": f"set_vat_vat0_{preview_id}"}],
                [{"text": "НДС 10%", "callback_data": f"set_vat_vat10_{preview_id}"}],
                [{"text": "НДС 20%", "callback_data": f"set_vat_vat20_{preview_id}"}],
                [{"text": "« Назад", "callback_data": f"edit_group_items_{preview_id}"}]
            ]
            
            edit_message_with_buttons(bot_token, chat_id, message_id, prompt_text, vat_buttons)
            return create_response({'ok': True})
        elif callback_data.startswith('edit_payment_object_'):
            field = 'payment_object'
            preview_id = callback_data.replace('edit_payment_object_', '')
            prompt_text = "📦 <b>Выбери предмет расчета:</b>"
            
            object_buttons = [
                [{"text": "Товар", "callback_data": f"set_payment_object_commodity_{preview_id}"}],
                [{"text": "Услуга", "callback_data": f"set_payment_object_service_{preview_id}"}],
                [{"text": "Работа", "callback_data": f"set_payment_object_job_{preview_id}"}],
                [{"text": "« Назад", "callback_data": f"edit_group_items_{preview_id}"}]
            ]
            
            edit_message_with_buttons(bot_token, chat_id, message_id, prompt_text, object_buttons)
            return create_response({'ok': True})
        elif callback_data.startswith('edit_payment_method_'):
            field = 'payment_method'
            preview_id = callback_data.replace('edit_payment_method_', '')
            prompt_text = "💵 <b>Выбери признак расчета:</b>"
            
            method_buttons = [
                [{"text": "Полный расчет", "callback_data": f"set_payment_method_full_payment_{preview_id}"}],
                [{"text": "Предоплата 100%", "callback_data": f"set_payment_method_full_prepayment_{preview_id}"}],
                [{"text": "Предоплата", "callback_data": f"set_payment_method_prepayment_{preview_id}"}],
                [{"text": "Аванс", "callback_data": f"set_payment_method_advance_{preview_id}"}],
                [{"text": "Частичный расчет", "callback_data": f"set_payment_method_partial_payment_{preview_id}"}],
                [{"text": "Кредит", "callback_data": f"set_payment_method_credit_{preview_id}"}],
                [{"text": "« Назад", "callback_data": f"edit_group_items_{preview_id}"}]
            ]
            
            edit_message_with_buttons(bot_token, chat_id, message_id, prompt_text, method_buttons)
            return create_response({'ok': True})
        elif callback_data.startswith('edit_payment_type_'):
            field = 'payment_type'
            preview_id = callback_data.replace('edit_payment_type_', '')
            prompt_text = "💳 <b>Выбери тип оплаты:</b>"
            
            payment_buttons = [
                [{"text": "💵 Наличные", "callback_data": f"set_payment_0_{preview_id}"}],
                [{"text": "💳 Безналичный", "callback_data": f"set_payment_1_{preview_id}"}],
                [{"text": "📝 Предоплата", "callback_data": f"set_payment_2_{preview_id}"}],
                [{"text": "🏦 Кредит", "callback_data": f"set_payment_3_{preview_id}"}],
                [{"text": "« Назад", "callback_data": f"edit_group_payment_{preview_id}"}]
            ]
            
            edit_message_with_buttons(bot_token, chat_id, message_id, prompt_text, payment_buttons)
            return create_response({'ok': True})
        elif callback_data.startswith('edit_payment_sum_'):
            field = 'payment_sum'
            preview_id = callback_data.replace('edit_payment_sum_', '')
            prompt_text = "💰 <b>Изменить сумму оплаты</b>\n\nОтправь новую сумму числом.\n\nНапример: <code>1500</code>"
        elif callback_data.startswith('edit_sno_'):
            field = 'sno'
            preview_id = callback_data.replace('edit_sno_', '')
            prompt_text = "💼 <b>Выбери систему налогообложения:</b>"
            
            sno_buttons = [
                [{"text": "УСН доход", "callback_data": f"set_sno_usn_income_{preview_id}"}],
                [{"text": "УСН доход-расход", "callback_data": f"set_sno_usn_income_outcome_{preview_id}"}],
                [{"text": "ОСНО", "callback_data": f"set_sno_osn_{preview_id}"}],
                [{"text": "ЕСХН", "callback_data": f"set_sno_esn_{preview_id}"}],
                [{"text": "Патент", "callback_data": f"set_sno_patent_{preview_id}"}],
                [{"text": "« Назад", "callback_data": f"edit_group_company_{preview_id}"}]
            ]
            
            edit_message_with_buttons(bot_token, chat_id, message_id, prompt_text, sno_buttons)
            return create_response({'ok': True})
        elif callback_data.startswith('edit_payment_address_'):
            field = 'payment_address'
            preview_id = callback_data.replace('edit_payment_address_', '')
            prompt_text = "📍 <b>Изменить адрес расчетов</b>\n\nОтправь новый адрес текстом.\n\nНапример: <code>example.com</code>"
        elif callback_data.startswith('edit_operation_type_'):
            field = 'operation_type'
            preview_id = callback_data.replace('edit_operation_type_', '')
            prompt_text = "🔄 <b>Выбери тип операции:</b>"
            
            operation_buttons = [
                [{"text": "🛒 Приход (продажа)", "callback_data": f"set_operation_sell_{preview_id}"}],
                [{"text": "↩️ Возврат прихода", "callback_data": f"set_operation_refund_{preview_id}"}],
                [{"text": "📝 Коррекция прихода", "callback_data": f"set_operation_sell_correction_{preview_id}"}],
                [{"text": "📝 Коррекция расхода", "callback_data": f"set_operation_refund_correction_{preview_id}"}],
                [{"text": "« Назад", "callback_data": f"edit_{preview_id}"}]
            ]
            
            edit_message_with_buttons(bot_token, chat_id, message_id, prompt_text, operation_buttons)
            return create_response({'ok': True})
        elif callback_data.startswith('edit_email_'):
            field = 'email'
            preview_id = callback_data.replace('edit_email_', '')
            prompt_text = "📧 <b>Изменить email клиента</b>\n\nОтправь новый email текстом.\n\nНапример: <code>client@mail.ru</code>"
        elif callback_data.startswith('edit_phone_'):
            field = 'phone'
            preview_id = callback_data.replace('edit_phone_', '')
            prompt_text = "📱 <b>Изменить телефон клиента</b>\n\nОтправь новый телефон текстом.\n\nНапример: <code>+79991234567</code>"
        
        # Save editing state
        print(f"[DEBUG] About to call save_editing_state with preview_id='{preview_id}', field='{field}'")
        save_editing_state(preview_id, field)
        print(f"[DEBUG] save_editing_state completed, now sending prompt message")
        
        edit_message(bot_token, chat_id, message_id, prompt_text)
    
    elif callback_data.startswith('show_receipt_'):
        # Show receipt text/content
        preview_id = callback_data.replace('show_receipt_', '')
        preview_data = get_preview_data(preview_id)
        
        if not preview_data:
            edit_message(bot_token, chat_id, message_id, "❌ Ошибка: данные не найдены")
            return create_response({'ok': True})
        
        receipt_data = preview_data.get('receipt_data', {})
        user_message = preview_data.get('user_message', 'Не указано')
        
        receipt_text = "🧾 <b>Содержимое чека</b>\n\n"
        receipt_text += f"<b>Оригинальный запрос:</b>\n<code>{user_message}</code>\n\n"
        receipt_text += f"<b>Чек ID:</b> <code>{preview_id}</code>\n"
        
        if receipt_data.get('items'):
            receipt_text += f"\n<b>Товары:</b>\n"
            for idx, item in enumerate(receipt_data['items'], 1):
                receipt_text += f"{idx}. {item.get('name', 'Товар')} - {item.get('price', 0)}₽\n"
        
        back_buttons = [
            [{"text": "« Назад", "callback_data": f"edit_group_doc_{preview_id}"}]
        ]
        
        edit_message_with_buttons(bot_token, chat_id, message_id, receipt_text, back_buttons)
    
    elif callback_data.startswith('edit_payment_link_'):
        # Edit payment link - show payment providers
        preview_id = callback_data.replace('edit_payment_link_', '')
        preview_data = get_preview_data(preview_id)
        
        if not preview_data:
            edit_message(bot_token, chat_id, message_id, "❌ Ошибка: данные не найдены")
            return create_response({'ok': True})
        
        user_id = preview_data.get('user_id', '')
        
        # Load payment providers from Ecomkassa API
        payment_providers = get_payment_providers(user_id)
        
        if not payment_providers:
            edit_message(bot_token, chat_id, message_id, "❌ Не удалось загрузить список платежных провайдеров. Проверь настройки ЕкомКасса.")
            return create_response({'ok': True})
        
        prompt_text = "🔗 <b>Выбери платежного провайдера:</b>\n\nДля создания чека со ссылкой на оплату"
        
        provider_buttons = []
        for provider in payment_providers:
            provider_id = provider.get('id')
            provider_desc = provider.get('description', f'Провайдер {provider_id}')
            
            # Clean provider description: remove specific prefixes
            provider_desc = provider_desc.replace('Платёж через счёт ', '')
            provider_desc = provider_desc.replace('Платёж через эквайринг ', '')
            provider_desc = provider_desc.replace('Платёж через ', '')
            # Remove quotes around provider names
            provider_desc = provider_desc.replace('"', '')
            
            provider_buttons.append([{
                "text": provider_desc,
                "callback_data": f"set_payment_provider_{provider_id}_{preview_id}"
            }])
        
        provider_buttons.append([{"text": "« Назад", "callback_data": f"edit_group_doc_{preview_id}"}])
        
        edit_message_with_buttons(bot_token, chat_id, message_id, prompt_text, provider_buttons)
    
    # CRITICAL: edit_group_ MUST be checked BEFORE general edit_ to avoid false matches
    elif callback_data.startswith('edit_group_'):
        # Handle group menu selections
        # Format: edit_group_doc_265009146_1764234824 -> group_type=doc, preview_id=265009146_1764234824
        # Format: edit_group_company_265009146_1764234824 -> group_type=company, preview_id=265009146_1764234824
        
        # Remove prefix 'edit_group_'
        remaining = callback_data.replace('edit_group_', '', 1)
        
        # Group types: doc, company, client, items, payment
        # Preview ID format: chat_id_timestamp (e.g., 265009146_1764234824)
        # We need to extract group_type (one of known types) and preview_id (rest)
        
        known_groups = ['doc', 'company', 'client', 'items', 'payment']
        group_type = ''
        preview_id = ''
        
        for group in known_groups:
            if remaining.startswith(group + '_'):
                group_type = group
                preview_id = remaining[len(group) + 1:]  # +1 for underscore
                break
        
        if not group_type:
            # Fallback to old logic if no match
            parts = remaining.split('_', 1)
            group_type = parts[0]
            preview_id = parts[1] if len(parts) > 1 else ''
        
        print(f"[DEBUG] edit_group_ callback: callback_data='{callback_data}'")
        print(f"[DEBUG] edit_group_ callback: remaining='{remaining}', group_type='{group_type}', preview_id='{preview_id}'")
        
        if not preview_id:
            print(f"[ERROR] preview_id is empty! callback_data='{callback_data}', remaining='{remaining}'")
            edit_message(bot_token, chat_id, message_id, f"❌ Ошибка: не удалось извлечь preview_id из callback_data")
            return create_response({'ok': True})
        
        preview_data = get_preview_data(preview_id)
        print(f"[DEBUG] preview_data retrieved: {preview_data is not None}")
        
        if not preview_data:
            print(f"[ERROR] preview_data not found in DB for preview_id: '{preview_id}'")
            edit_message(bot_token, chat_id, message_id, f"❌ Ошибка: данные не найдены (preview_id: {preview_id})")
            return create_response({'ok': True})
        
        if group_type == 'doc':
            # Тип документа
            receipt_data = preview_data.get('receipt_data', {})
            payment_link_enabled = receipt_data.get('payment_link_enabled', False)
            provider_name = receipt_data.get('payment_provider_name', '')
            
            if payment_link_enabled and provider_name:
                group_text = f"📄 <b>Тип документа</b>\n\n✅ Провайдер: <b>{provider_name}</b>\n⚠️ Тип операции: <b>Продажа</b> (фиксировано)\n\nВыбери параметр:"
                group_buttons = [
                    [{"text": "🧾 Чек", "callback_data": f"show_receipt_{preview_id}"}],
                    [{"text": "🔗 Изменить провайдера", "callback_data": f"edit_payment_link_{preview_id}"}],
                    [{"text": "« Назад", "callback_data": f"edit_{preview_id}"}]
                ]
            else:
                group_text = "📄 <b>Тип документа</b>\n\nВыбери параметр:"
                group_buttons = [
                    [{"text": "🧾 Чек", "callback_data": f"show_receipt_{preview_id}"}],
                    [{"text": "🔗 Ссылка на оплату", "callback_data": f"edit_payment_link_{preview_id}"}],
                    [{"text": "🔄 Тип операции", "callback_data": f"edit_operation_type_{preview_id}"}],
                    [{"text": "« Назад", "callback_data": f"edit_{preview_id}"}]
                ]
        elif group_type == 'company':
            # Данные компании
            group_text = "🏢 <b>Данные компании</b>\n\nВыбери параметр:"
            group_buttons = [
                [{"text": "💼 СНО", "callback_data": f"edit_sno_{preview_id}"}],
                [{"text": "📍 Адрес расчетов", "callback_data": f"edit_payment_address_{preview_id}"}],
                [{"text": "« Назад", "callback_data": f"edit_{preview_id}"}]
            ]
        elif group_type == 'client':
            # Данные клиента
            group_text = "👤 <b>Данные клиента</b>\n\nВыбери параметр:"
            group_buttons = [
                [{"text": "📧 Email клиента", "callback_data": f"edit_email_{preview_id}"}],
                [{"text": "📱 Телефон клиента", "callback_data": f"edit_phone_{preview_id}"}],
                [{"text": "« Назад", "callback_data": f"edit_{preview_id}"}]
            ]
        elif group_type == 'items':
            # Товары и услуги
            group_text = "🛒 <b>Товары и услуги</b>\n\nВыбери параметр:"
            group_buttons = [
                [{"text": "📝 Название", "callback_data": f"edit_item_{preview_id}"}],
                [{"text": "💰 Цена", "callback_data": f"edit_price_{preview_id}"}],
                [{"text": "📊 Количество", "callback_data": f"edit_quantity_{preview_id}"}],
                [{"text": "📏 Ед. измерения", "callback_data": f"edit_measure_{preview_id}"}],
                [{"text": "🧾 НДС", "callback_data": f"edit_vat_{preview_id}"}],
                [{"text": "📦 Предмет расчета", "callback_data": f"edit_payment_object_{preview_id}"}],
                [{"text": "💵 Признак расчета", "callback_data": f"edit_payment_method_{preview_id}"}],
                [{"text": "« Назад", "callback_data": f"edit_{preview_id}"}]
            ]
        elif group_type == 'payment':
            # Способ оплаты
            receipt_data = preview_data.get('receipt_data', {})
            payment_link_enabled = receipt_data.get('payment_link_enabled', False)
            
            if payment_link_enabled:
                provider_name = receipt_data.get('payment_provider_name', 'Не указан')
                group_text = f"💳 <b>Способ оплаты</b>\n\n⚠️ Тип оплаты: <b>Ссылка на оплату ({provider_name})</b>\n(фиксировано для платежа через провайдера)\n\nВыбери параметр:"
                group_buttons = [
                    [{"text": "💰 Сумма", "callback_data": f"edit_payment_sum_{preview_id}"}],
                    [{"text": "« Назад", "callback_data": f"edit_{preview_id}"}]
                ]
            else:
                group_text = "💳 <b>Способ оплаты</b>\n\nВыбери параметр:"
                group_buttons = [
                    [{"text": "💳 Тип оплаты", "callback_data": f"edit_payment_type_{preview_id}"}],
                    [{"text": "💰 Сумма", "callback_data": f"edit_payment_sum_{preview_id}"}],
                    [{"text": "« Назад", "callback_data": f"edit_{preview_id}"}]
                ]
        else:
            edit_message(bot_token, chat_id, message_id, "❌ Неизвестная группа")
            return create_response({'ok': True})
        
        edit_message_with_buttons(bot_token, chat_id, message_id, group_text, group_buttons)
    
    elif callback_data.startswith('set_payment_provider_'):
        print(f"[DEBUG] set_payment_provider_ handler triggered")
        parts = callback_data.replace('set_payment_provider_', '').split('_')
        provider_id = parts[0]
        preview_id = '_'.join(parts[1:])
        print(f"[DEBUG] Parsed: provider_id={provider_id}, preview_id={preview_id}")
        
        preview_data = get_preview_data(preview_id)
        print(f"[DEBUG] preview_data loaded: {preview_data is not None}")
        if not preview_data:
            print(f"[ERROR] No preview_data found for preview_id: {preview_id}")
            edit_message(bot_token, chat_id, message_id, "❌ Ошибка: данные не найдены")
            return create_response({'ok': True})
        
        user_id = preview_data.get('user_id', '')
        print(f"[DEBUG] user_id={user_id}")
        
        # Load payment providers to get provider name
        payment_providers = get_payment_providers(user_id)
        print(f"[DEBUG] payment_providers loaded: {payment_providers is not None}")
        provider_name = f"Провайдер {provider_id}"
        
        if payment_providers:
            for provider in payment_providers:
                if str(provider.get('id')) == str(provider_id):
                    provider_desc = provider.get('description', '')
                    # Clean provider description
                    provider_desc = provider_desc.replace('Платёж через счёт ', '')
                    provider_desc = provider_desc.replace('Платёж через эквайринг ', '')
                    provider_desc = provider_desc.replace('Платёж через ', '')
                    provider_desc = provider_desc.replace('"', '')
                    provider_name = provider_desc
                    print(f"[DEBUG] Found provider name: {provider_name}")
                    break
        
        print(f"[DEBUG] Final provider_name: {provider_name}")
        
        # Update payment provider in preview data with name
        success = update_preview_payment_provider(preview_id, provider_id, provider_name)
        print(f"[DEBUG] update_preview_payment_provider returned: {success}")
        
        if not success:
            print(f"[ERROR] Failed to update payment provider")
            edit_message(bot_token, chat_id, message_id, "❌ Ошибка при сохранении провайдера")
            return create_response({'ok': True})
        
        # Return to "Тип документа" menu
        print(f"[DEBUG] Preparing menu response")
        group_text = f"📄 <b>Тип документа</b>\n\n✅ Выбран провайдер: <b>{provider_name}</b>\n\nВыбери параметр:"
        group_buttons = [
            [{"text": "🧾 Чек", "callback_data": f"show_receipt_{preview_id}"}],
            [{"text": "🔗 Изменить провайдера", "callback_data": f"edit_payment_link_{preview_id}"}],
            [{"text": "🔄 Тип операции", "callback_data": f"edit_operation_type_{preview_id}"}],
            [{"text": "« Назад", "callback_data": f"edit_{preview_id}"}]
        ]
        
        print(f"[DEBUG] Calling edit_message_with_buttons")
        edit_message_with_buttons(bot_token, chat_id, message_id, group_text, group_buttons)
        print(f"[DEBUG] edit_message_with_buttons completed")
        return create_response({'ok': True})
    
    elif callback_data.startswith('edit_'):
        # General edit handler - shows main edit menu with groups
        preview_id = callback_data.replace('edit_', '')
        preview_data = get_preview_data(preview_id)
        
        if not preview_data:
            edit_message(bot_token, chat_id, message_id, "❌ Ошибка: данные не найдены")
            return create_response({'ok': True})
        
        # Show main edit menu with groups
        edit_text = "✏️ <b>Что изменить?</b>\n\nВыбери раздел для редактирования:"
        
        edit_buttons = [
            [{"text": "📄 Тип документа", "callback_data": f"edit_group_doc_{preview_id}"}],
            [{"text": "🏢 Данные компании", "callback_data": f"edit_group_company_{preview_id}"}],
            [{"text": "👤 Данные клиента", "callback_data": f"edit_group_client_{preview_id}"}],
            [{"text": "🛒 Товары и услуги", "callback_data": f"edit_group_items_{preview_id}"}],
            [{"text": "💳 Способ оплаты", "callback_data": f"edit_group_payment_{preview_id}"}],
            [{"text": "« Назад к чеку", "callback_data": f"back_{preview_id}"}]
        ]
        
        edit_message_with_buttons(bot_token, chat_id, message_id, edit_text, edit_buttons)
    
    elif callback_data.startswith('back_'):
        preview_id = callback_data.replace('back_', '')
        preview_data = get_preview_data(preview_id)
        
        if not preview_data:
            edit_message(bot_token, chat_id, message_id, "❌ Ошибка: данные не найдены")
            return create_response({'ok': True})
        
        user_id = preview_data['user_id']
        
        # CRITICAL: Use stored receipt_data instead of regenerating
        # This preserves payment_link and other edits
        receipt_data = preview_data.get('receipt_data')
        
        if receipt_data:
            # Use stored edited data
            items = receipt_data.get('items', [])
            total = receipt_data.get('total', 0)
            payments = receipt_data.get('payments', [])
            client_data = receipt_data.get('client', {})
            operation_type = receipt_data.get('operation_type', 'sell')
            
            operation_names = {
                'sell': 'Приход',
                'refund': 'Возврат прихода',
                'sell_correction': 'Коррекция прихода',
                'refund_correction': 'Коррекция расхода'
            }
            
            response_text = "📋 <b>Проверь перед отправкой:</b>\n\n"
            
            # Document type with provider on same line for payment links
            payment_link_enabled = receipt_data.get('payment_link_enabled', False)
            company_data_back = receipt_data.get('company', {})
            
            if payment_link_enabled:
                provider_name = receipt_data.get('payment_provider_name', 'Не выбран')
                response_text += f"<b>Тип документа:</b> 🔗 Платежная ссылка Провайдер: {provider_name}\n"
            else:
                response_text += f"<b>Тип документа:</b> 🧾 Чек\n"
            
            response_text += f"<b>Тип операции:</b> {operation_names.get(operation_type, operation_type)}\n\n"
            
            # Company info (SNO and payment address) IMMEDIATELY after operation type
            sno_back = company_data_back.get('sno', 'usn_income')
            payment_address_back = company_data_back.get('payment_address', '')
            
            sno_names_back = {
                'usn_income': 'УСН доход',
                'usn_income_outcome': 'УСН доход-расход',
                'osn': 'ОСНО',
                'esn': 'ЕСХН',
                'patent': 'Патент'
            }
            
            response_text += f"<b>💼 СНО:</b> {sno_names_back.get(sno_back, sno_back)}\n"
            if payment_address_back:
                response_text += f"<b>📍 Адрес расчетов:</b> {payment_address_back}\n"
            
            response_text += f"<b>📧 Email клиента:</b> {client_data.get('email', 'Не указан')}\n"
            
            response_text += "\n<b>Товары/Услуги:</b>\n"
            for idx, item in enumerate(items, 1):
                name = item.get('name', 'Товар')
                price = item.get('price', 0)
                qty = item.get('quantity', 1)
                measure = item.get('measure', 'шт')
                vat = item.get('vat', 'none')
                payment_method = item.get('payment_method', 'full_payment')
                payment_object = item.get('payment_object', 'commodity')
                
                vat_names = {'none': 'Без НДС', 'vat0': 'НДС 0%', 'vat10': 'НДС 10%', 'vat20': 'НДС 20%'}
                method_names = {
                    'full_payment': 'Полный расчёт',
                    'prepayment': 'Предоплата',
                    'advance': 'Аванс',
                    'full_prepayment': 'Предоплата 100%',
                    'partial_payment': 'Частичный расчёт',
                    'credit': 'Кредит',
                    'credit_payment': 'Оплата кредита'
                }
                object_names = {'commodity': 'Товар', 'service': 'Услуга', 'excise': 'Подакцизный товар', 'job': 'Работа'}
                
                response_text += f"\n<b>{idx}. {name}</b>\n"
                response_text += f"   Цена: {price}₽ × {qty} {measure}\n"
                response_text += f"   НДС: {vat_names.get(vat, vat)}\n"
                response_text += f"   Предмет: {object_names.get(payment_object, payment_object)}\n"
                response_text += f"   Способ: {method_names.get(payment_method, payment_method)}\n"
            
            response_text += f"\n<b>💰 Итого:</b> {total}₽\n\n"
            
            # Payment details - same as show_receipt_preview
            if payment_link_enabled:
                # For payment links, payment method is always "Безналичный" (from provider)
                response_text += f"<b>Способ оплаты:</b> 💳 Безналичный\n"
            elif payments and len(payments) > 1:
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
            
            # CRITICAL: Check balance between items total and payments total
            # Calculate items total
            items_total = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
            # Calculate payments total
            payments_total = sum(payment.get('sum', 0) for payment in payments)
            
            # Check if balanced (with 0.01 tolerance for float precision)
            difference = round(items_total - payments_total, 2)
            
            if abs(difference) > 0.01:
                if difference > 0:
                    # Items cost more than paid - client needs to pay more
                    response_text += f"\n⚠️ <b>Недоплата:</b> {abs(difference)}₽\n"
                    response_text += f"<i>Клиент должен доплатить {abs(difference)}₽</i>\n"
                else:
                    # Paid more than items cost - need to return money
                    response_text += f"\n⚠️ <b>Переплата:</b> {abs(difference)}₽\n"
                    response_text += f"<i>Нужно вернуть клиенту {abs(difference)}₽</i>\n"
            
            edit_message_with_buttons(
                bot_token,
                chat_id,
                message_id,
                response_text,
                [
                    [{"text": "✅ Отправить запрос", "callback_data": f"confirm_{preview_id}"}],
                    [{"text": "✏️ Изменить", "callback_data": f"edit_{preview_id}"}],
                    [{"text": "❌ Отменить", "callback_data": f"cancel_{preview_id}"}]
                ]
            )
    
    elif callback_data.startswith('set_payment_'):
        # Extract payment type and preview_id
        parts = callback_data.replace('set_payment_', '').split('_')
        payment_type = parts[0]
        preview_id = '_'.join(parts[1:])
        
        preview_data = get_preview_data(preview_id)
        if not preview_data:
            edit_message(bot_token, chat_id, message_id, "❌ Ошибка: данные не найдены")
            return create_response({'ok': True})
        
        # Update payment type in preview data
        update_preview_payment(preview_id, payment_type)
        
        edit_message(bot_token, chat_id, message_id, "✅ Способ оплаты изменен!\n\nВозвращаю к чеку...")
        
        # Wait a bit and show updated preview
        import time
        time.sleep(1)
        
        # Trigger back button logic
        callback_query['data'] = f"back_{preview_id}"
        return handle_callback_query(callback_query, bot_token)
    
    elif callback_data.startswith('set_operation_'):
        # Extract operation type and preview_id
        parts = callback_data.replace('set_operation_', '').split('_')
        operation_type = parts[0]
        preview_id = '_'.join(parts[1:])
        
        preview_data = get_preview_data(preview_id)
        if not preview_data:
            edit_message(bot_token, chat_id, message_id, "❌ Ошибка: данные не найдены")
            return create_response({'ok': True})
        
        # Update operation type in preview data
        update_preview_operation_type(preview_id, operation_type)
        
        operation_names = {
            'sell': '🛒 Приход (продажа)',
            'refund': '↩️ Возврат прихода',
            'sell_correction': '📝 Коррекция прихода',
            'refund_correction': '📝 Коррекция расхода'
        }
        
        edit_message(bot_token, chat_id, message_id, f"✅ Тип операции изменен на: {operation_names.get(operation_type, operation_type)}\n\nВозвращаю к чеку...")
        
        # Wait a bit and show updated preview
        import time
        time.sleep(1)
        
        # Trigger back button logic
        callback_query['data'] = f"back_{preview_id}"
        return handle_callback_query(callback_query, bot_token)
    
    elif callback_data.startswith('set_measure_'):
        parts = callback_data.replace('set_measure_', '').split('_')
        measure = parts[0]
        preview_id = '_'.join(parts[1:])
        
        update_preview_field_value(preview_id, 'measure', measure)
        
        edit_message(bot_token, chat_id, message_id, f"✅ Единица измерения изменена на: {measure}\n\nВозвращаю к чеку...")
        
        import time
        time.sleep(1)
        
        callback_query['data'] = f"back_{preview_id}"
        return handle_callback_query(callback_query, bot_token)
    
    elif callback_data.startswith('set_vat_'):
        parts = callback_data.replace('set_vat_', '').split('_')
        vat = parts[0]
        preview_id = '_'.join(parts[1:])
        
        update_preview_field_value(preview_id, 'vat', vat)
        
        vat_names = {'none': 'Без НДС', 'vat0': 'НДС 0%', 'vat10': 'НДС 10%', 'vat20': 'НДС 20%'}
        edit_message(bot_token, chat_id, message_id, f"✅ НДС изменен на: {vat_names.get(vat, vat)}\n\nВозвращаю к чеку...")
        
        import time
        time.sleep(1)
        
        callback_query['data'] = f"back_{preview_id}"
        return handle_callback_query(callback_query, bot_token)
    
    elif callback_data.startswith('set_payment_object_'):
        parts = callback_data.replace('set_payment_object_', '').split('_')
        payment_object = parts[0]
        preview_id = '_'.join(parts[1:])
        
        update_preview_field_value(preview_id, 'payment_object', payment_object)
        
        object_names = {'commodity': 'Товар', 'service': 'Услуга', 'job': 'Работа'}
        edit_message(bot_token, chat_id, message_id, f"✅ Предмет расчета изменен на: {object_names.get(payment_object, payment_object)}\n\nВозвращаю к чеку...")
        
        import time
        time.sleep(1)
        
        callback_query['data'] = f"back_{preview_id}"
        return handle_callback_query(callback_query, bot_token)
    
    elif callback_data.startswith('set_payment_method_'):
        parts = callback_data.replace('set_payment_method_', '').split('_')
        payment_method = '_'.join(parts[:-1]) if len(parts) > 1 else parts[0]
        # Extract preview_id which is the last part after splitting by '_'
        preview_id_parts = callback_data.split('_')
        preview_id = preview_id_parts[-1]
        
        update_preview_field_value(preview_id, 'payment_method', payment_method)
        
        method_names = {
            'full_payment': 'Полный расчет',
            'full_prepayment': 'Предоплата 100%',
            'prepayment': 'Предоплата',
            'advance': 'Аванс',
            'partial_payment': 'Частичный расчет',
            'credit': 'Кредит'
        }
        edit_message(bot_token, chat_id, message_id, f"✅ Признак расчета изменен на: {method_names.get(payment_method, payment_method)}\n\nВозвращаю к чеку...")
        
        import time
        time.sleep(1)
        
        callback_query['data'] = f"back_{preview_id}"
        return handle_callback_query(callback_query, bot_token)
    
    elif callback_data.startswith('set_sno_'):
        parts = callback_data.replace('set_sno_', '').split('_')
        sno = '_'.join(parts[:-1]) if len(parts) > 1 else parts[0]
        preview_id_parts = callback_data.split('_')
        preview_id = preview_id_parts[-1]
        
        update_preview_field_value(preview_id, 'sno', sno)
        
        sno_names = {
            'usn_income': 'УСН доход',
            'usn_income_outcome': 'УСН доход-расход',
            'osn': 'ОСНО',
            'esn': 'ЕСХН',
            'patent': 'Патент'
        }
        edit_message(bot_token, chat_id, message_id, f"✅ СНО изменена на: {sno_names.get(sno, sno)}\n\nВозвращаю к чеку...")
        
        import time
        time.sleep(1)
        
        callback_query['data'] = f"back_{preview_id}"
        return handle_callback_query(callback_query, bot_token)
    
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


def store_preview_data(preview_id: str, preview_data: Dict[str, Any], chat_id: int) -> None:
    '''Store preview data in database for later confirmation'''
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        print("[ERROR] DATABASE_URL not set")
        return
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        # Ensure table exists
        cur.execute(
            "CREATE TABLE IF NOT EXISTS telegram_previews ("
            "preview_id TEXT PRIMARY KEY, "
            "chat_id BIGINT, "
            "user_message TEXT, "
            "user_id TEXT, "
            "receipt_data JSONB, "
            "payment_type TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        
        # Extract data from preview_data dict
        user_message = preview_data.get('user_message', '')
        user_id = preview_data.get('user_id', '')
        receipt_data = preview_data.get('receipt_data')
        
        # Insert or update
        cur.execute(
            "INSERT INTO telegram_previews (preview_id, chat_id, user_message, user_id, receipt_data, created_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW()) "
            "ON CONFLICT (preview_id) DO UPDATE SET "
            "chat_id = EXCLUDED.chat_id, "
            "user_message = EXCLUDED.user_message, "
            "user_id = EXCLUDED.user_id, "
            "receipt_data = EXCLUDED.receipt_data, "
            "created_at = NOW()",
            (preview_id, chat_id, user_message, user_id, json.dumps(receipt_data) if receipt_data else None)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"[DEBUG] Preview data stored successfully: preview_id={preview_id}")
    except Exception as e:
        print(f"[ERROR] Failed to store preview data: {e}")


def save_preview_data(chat_id: int, user_message: str, user_id: str, receipt_data: dict = None) -> str:
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
            "receipt_data JSONB, "
            "payment_type TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        
        # Add receipt_data column if it doesn't exist
        cur.execute(
            "ALTER TABLE telegram_previews ADD COLUMN IF NOT EXISTS receipt_data JSONB"
        )
        
        # Add payment_type column if it doesn't exist
        cur.execute(
            "ALTER TABLE telegram_previews ADD COLUMN IF NOT EXISTS payment_type TEXT"
        )
        
        cur.execute(
            "INSERT INTO telegram_previews (preview_id, chat_id, user_message, user_id, receipt_data) "
            "VALUES (%s, %s, %s, %s, %s)",
            (preview_id, chat_id, user_message, user_id, json.dumps(receipt_data) if receipt_data else None)
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
        
        # Ensure telegram_previews table exists with all columns
        cur.execute(
            "CREATE TABLE IF NOT EXISTS telegram_previews ("
            "preview_id TEXT PRIMARY KEY, "
            "chat_id BIGINT, "
            "user_message TEXT, "
            "user_id TEXT, "
            "receipt_data JSONB, "
            "payment_type TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        
        cur.execute(
            "ALTER TABLE telegram_previews ADD COLUMN IF NOT EXISTS receipt_data JSONB"
        )
        
        cur.execute(
            "SELECT user_message, user_id, receipt_data FROM telegram_previews WHERE preview_id = %s",
            (preview_id,)
        )
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result:
            return {
                'user_message': result[0],
                'user_id': result[1],
                'receipt_data': result[2] if result[2] else None
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


def edit_message_with_buttons(bot_token: str, chat_id: int, message_id: int, text: str, buttons: list) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    data = {
        'chat_id': chat_id,
        'message_id': message_id,
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
    
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[ERROR] Failed to edit message with buttons: {e}")


def save_editing_state(preview_id: str, field: str) -> None:
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        print(f"[ERROR] No DATABASE_URL, cannot save editing state")
        return
    
    print(f"[DEBUG] save_editing_state called with preview_id='{preview_id}', field='{field}'")
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute(
            "CREATE TABLE IF NOT EXISTS telegram_edit_states ("
            "preview_id TEXT PRIMARY KEY, "
            "field TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        
        print(f"[DEBUG] Inserting into telegram_edit_states: preview_id='{preview_id}', field='{field}'")
        
        cur.execute(
            "INSERT INTO telegram_edit_states (preview_id, field) "
            "VALUES (%s, %s) "
            "ON CONFLICT (preview_id) DO UPDATE SET field = EXCLUDED.field, created_at = CURRENT_TIMESTAMP",
            (preview_id, field)
        )
        
        print(f"[DEBUG] INSERT successful, affected rows: {cur.rowcount}")
        
        conn.commit()
        print(f"[DEBUG] Committed successfully")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Failed to save editing state: {e}")


def get_editing_state(preview_id: str) -> Optional[str]:
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return None
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute(
            "SELECT field FROM telegram_edit_states WHERE preview_id = %s",
            (preview_id,)
        )
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result:
            return result[0]
        
        return None
    except Exception as e:
        print(f"[ERROR] Failed to get editing state: {e}")
        return None


def delete_editing_state(preview_id: str) -> None:
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute("DELETE FROM telegram_edit_states WHERE preview_id = %s", (preview_id,))
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Failed to delete editing state: {e}")


def update_preview_payment(preview_id: str, payment_type: str) -> None:
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        # Add payment_type column if not exists
        cur.execute(
            "ALTER TABLE telegram_previews ADD COLUMN IF NOT EXISTS payment_type TEXT"
        )
        
        cur.execute(
            "UPDATE telegram_previews SET payment_type = %s WHERE preview_id = %s",
            (payment_type, preview_id)
        )
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Failed to update payment type: {e}")


def find_editing_preview_for_chat(chat_id: int) -> Optional[str]:
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return None
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        # Ensure telegram_edit_states table exists
        cur.execute(
            "CREATE TABLE IF NOT EXISTS telegram_edit_states ("
            "preview_id TEXT PRIMARY KEY, "
            "field TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        
        # Ensure telegram_previews has chat_id column
        cur.execute(
            "CREATE TABLE IF NOT EXISTS telegram_previews ("
            "preview_id TEXT PRIMARY KEY, "
            "chat_id BIGINT, "
            "user_message TEXT, "
            "user_id TEXT, "
            "receipt_data JSONB, "
            "payment_type TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        
        cur.execute(
            "ALTER TABLE telegram_previews ADD COLUMN IF NOT EXISTS chat_id BIGINT"
        )
        
        # Find most recent preview for this chat that has editing state
        print(f"[DEBUG] Searching for preview with chat_id={chat_id}")
        
        # First check if there are any edit states at all
        cur.execute("SELECT COUNT(*) FROM telegram_edit_states")
        edit_states_count = cur.fetchone()[0]
        print(f"[DEBUG] Total edit_states in DB: {edit_states_count}")
        
        # Check if there are previews for this chat
        cur.execute("SELECT COUNT(*) FROM telegram_previews WHERE chat_id = %s", (chat_id,))
        previews_count = cur.fetchone()[0]
        print(f"[DEBUG] Previews for chat_id {chat_id}: {previews_count}")
        
        cur.execute(
            "SELECT p.preview_id FROM telegram_previews p "
            "JOIN telegram_edit_states e ON p.preview_id = e.preview_id "
            "WHERE p.chat_id = %s "
            "ORDER BY e.created_at DESC LIMIT 1",
            (chat_id,)
        )
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result:
            print(f"[DEBUG] Found preview_id: {result[0]}")
            return result[0]
        
        print(f"[DEBUG] No preview found for chat_id {chat_id}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to find editing preview: {e}")
        return None


def update_preview_field(preview_id: str, field: str, new_value: str, user_id: str) -> bool:
    """Update a specific field in preview data directly in receipt_data"""
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return False
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        # Ensure telegram_previews table exists with all columns
        cur.execute(
            "CREATE TABLE IF NOT EXISTS telegram_previews ("
            "preview_id TEXT PRIMARY KEY, "
            "chat_id BIGINT, "
            "user_message TEXT, "
            "user_id TEXT, "
            "receipt_data JSONB, "
            "payment_type TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        
        cur.execute(
            "ALTER TABLE telegram_previews ADD COLUMN IF NOT EXISTS receipt_data JSONB"
        )
        
        # Get current receipt_data
        cur.execute(
            "SELECT receipt_data FROM telegram_previews WHERE preview_id = %s",
            (preview_id,)
        )
        result = cur.fetchone()
        
        if not result or not result[0]:
            print(f"[ERROR] No receipt_data found for preview_id: {preview_id}")
            return False
        
        receipt_data = result[0]
        
        print(f"[DEBUG] Updating field '{field}' with value '{new_value}' for preview_id '{preview_id}'")
        print(f"[DEBUG] Current receipt_data type: {type(receipt_data)}")
        
        # Update specific field
        if field == 'item':
            if receipt_data.get('items') and len(receipt_data['items']) > 0:
                old_name = receipt_data['items'][0]['name']
                receipt_data['items'][0]['name'] = new_value
                print(f"[DEBUG] Updated item name: '{old_name}' -> '{new_value}'")
            else:
                print(f"[ERROR] No items found in receipt_data")
                return False
        elif field == 'price':
            try:
                price = float(new_value.replace('₽', '').replace('руб', '').strip())
                if receipt_data.get('items') and len(receipt_data['items']) > 0:
                    old_price = receipt_data['items'][0]['price']
                    receipt_data['items'][0]['price'] = price
                    
                    # CRITICAL: Recalculate total from ALL items
                    total = sum(item.get('price', 0) * item.get('quantity', 1) for item in receipt_data['items'])
                    receipt_data['total'] = round(total, 2)
                    
                    # Update payment sum to match new total
                    if receipt_data.get('payments'):
                        receipt_data['payments'][0]['sum'] = receipt_data['total']
                    
                    print(f"[DEBUG] Updated price: {old_price} -> {price}, new total: {receipt_data['total']}")
                else:
                    print(f"[ERROR] No items found in receipt_data")
                    return False
            except ValueError as ve:
                print(f"[ERROR] Invalid price value: {new_value}, error: {ve}")
                return False
        elif field == 'quantity':
            try:
                qty = float(new_value)
                if receipt_data.get('items') and len(receipt_data['items']) > 0:
                    old_qty = receipt_data['items'][0]['quantity']
                    receipt_data['items'][0]['quantity'] = qty
                    
                    # CRITICAL: Recalculate total from ALL items
                    total = sum(item.get('price', 0) * item.get('quantity', 1) for item in receipt_data['items'])
                    receipt_data['total'] = round(total, 2)
                    
                    # Update payment sum to match new total
                    if receipt_data.get('payments'):
                        receipt_data['payments'][0]['sum'] = receipt_data['total']
                    
                    print(f"[DEBUG] Updated quantity: {old_qty} -> {qty}, new total: {receipt_data['total']}")
                else:
                    print(f"[ERROR] No items found in receipt_data")
                    return False
            except ValueError as ve:
                print(f"[ERROR] Invalid quantity value: {new_value}, error: {ve}")
                return False
        elif field == 'email':
            if 'client' not in receipt_data:
                receipt_data['client'] = {}
            receipt_data['client']['email'] = new_value
            print(f"[DEBUG] Updated email to: {new_value}")
        elif field == 'phone':
            if 'client' not in receipt_data:
                receipt_data['client'] = {}
            receipt_data['client']['phone'] = new_value
            print(f"[DEBUG] Updated phone to: {new_value}")
        elif field == 'payment_sum':
            try:
                payment_sum = float(new_value.replace('₽', '').replace('руб', '').strip())
                if receipt_data.get('payments') and len(receipt_data['payments']) > 0:
                    receipt_data['payments'][0]['sum'] = payment_sum
                    # CRITICAL: DO NOT update total - it should always equal sum of items
                    # Balance validation will show the difference
                    print(f"[DEBUG] Updated payment sum to: {payment_sum} (total stays {receipt_data.get('total', 0)})")
                else:
                    print(f"[ERROR] No payments found in receipt_data")
                    return False
            except ValueError as ve:
                print(f"[ERROR] Invalid payment sum value: {new_value}, error: {ve}")
                return False
        elif field == 'payment_address':
            if 'company' not in receipt_data:
                receipt_data['company'] = {}
            receipt_data['company']['payment_address'] = new_value
            print(f"[DEBUG] Updated payment_address to: {new_value}")
        else:
            print(f"[ERROR] Unknown field: {field}")
            return False
        
        # Save updated receipt_data (psycopg2 handles dict -> JSONB conversion automatically)
        print(f"[DEBUG] Saving updated receipt_data to database...")
        cur.execute(
            "UPDATE telegram_previews SET receipt_data = %s WHERE preview_id = %s",
            (json.dumps(receipt_data), preview_id)
        )
        print(f"[DEBUG] Database update successful, affected rows: {cur.rowcount}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to update preview field: {e}")
        return False


def get_user_receipts_history(user_id: str, limit: int = 10) -> list:
    '''Get user's receipt history from database'''
    try:
        conn = get_db_connection()
        if not conn:
            print("[ERROR] No DB connection in get_user_receipts_history")
            return []
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, items, total, status, uuid, created_at, operation_type, payments
            FROM receipts 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT %s
        """, (user_id, limit))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        history = []
        for row in rows:
            items = json.loads(row[1]) if isinstance(row[1], str) else row[1]
            payments = json.loads(row[7]) if isinstance(row[7], str) else row[7]
            
            history.append({
                'id': row[0],
                'items': items,
                'total': float(row[2]),
                'status': row[3],
                'uuid': row[4],
                'created_at': row[5],
                'operation_type': row[6],
                'payments': payments
            })
        
        return history
    except Exception as e:
        print(f"[ERROR] Failed to get receipts history: {e}")
        return []


def get_receipt_by_id(receipt_id: int, user_id: str) -> Optional[Dict[str, Any]]:
    '''Get receipt data by ID for repeat functionality'''
    try:
        conn = get_db_connection()
        if not conn:
            print("[ERROR] No DB connection in get_receipt_by_id")
            return None
        cur = conn.cursor()
        
        # Load user settings for company data
        cur.execute("""
            SELECT company_email, inn, sno, payment_address
            FROM user_settings
            WHERE user_id = %s
        """, (user_id,))
        settings_row = cur.fetchone()
        
        if not settings_row:
            print(f"[ERROR] No user settings found for user_id: {user_id}")
            cur.close()
            conn.close()
            return None
        
        company_email = settings_row[0] or 'company@example.com'
        company_inn = settings_row[1] or ''
        company_sno = settings_row[2] or 'usn_income'
        company_payment_address = settings_row[3] or ''
        
        cur.execute("""
            SELECT items, total, payments, operation_type, customer_email, payment_type
            FROM receipts 
            WHERE id = %s AND user_id = %s
        """, (receipt_id, user_id))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            return None
        
        items = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        payments = json.loads(row[2]) if isinstance(row[2], str) else row[2]
        payment_type = row[5] or '103'
        
        # Determine document_type based on payment_type
        # payment_type >= 100 means it's a payment link
        try:
            payment_type_int = int(payment_type)
            document_type = 'link' if payment_type_int >= 100 else 'receipt'
            is_payment_link = payment_type_int >= 100
        except (ValueError, TypeError):
            document_type = 'receipt'
            is_payment_link = False
        
        # Get real provider name from Ecomkassa API
        provider_name = f'Провайдер {payment_type}'
        if is_payment_link:
            providers = get_payment_providers(user_id)
            if providers:
                for provider in providers:
                    if str(provider.get('id')) == str(payment_type):
                        provider_desc = provider.get('description', '')
                        # Clean provider description
                        provider_desc = provider_desc.replace('Платёж через счёт ', '')
                        provider_desc = provider_desc.replace('Платёж через эквайринг ', '')
                        provider_desc = provider_desc.replace('Платёж через ', '')
                        provider_desc = provider_desc.replace('"', '')
                        provider_name = provider_desc
                        break
        
        receipt_data = {
            'items': items,
            'total': float(row[1]),
            'payments': payments,
            'operation_type': row[3] or 'Приход',
            'customer_email': row[4],
            'payment_type': payment_type,
            'document_type': document_type,
            'payment_link_enabled': is_payment_link,
            'payment_provider_id': int(payment_type) if is_payment_link else None,
            'payment_provider_name': provider_name if is_payment_link else None,
            'company': {
                'email': company_email,
                'inn': company_inn,
                'sno': company_sno,
                'payment_address': company_payment_address
            },
            'client': {
                'email': row[4] or company_email,
                'phone': None
            }
        }
        
        return receipt_data
    except Exception as e:
        print(f"[ERROR] Failed to get receipt by ID: {e}")
        return None


def get_receipt_by_uuid(uuid_str: str, user_id: str) -> Optional[Dict[str, Any]]:
    '''Get receipt data by UUID for repeat functionality'''
    try:
        conn = get_db_connection()
        if not conn:
            print("[ERROR] No DB connection in get_receipt_by_uuid")
            return None
        cur = conn.cursor()
        
        # Load user settings for company data
        cur.execute("""
            SELECT company_email, inn, sno, payment_address
            FROM user_settings
            WHERE user_id = %s
        """, (user_id,))
        settings_row = cur.fetchone()
        
        if not settings_row:
            print(f"[ERROR] No user settings found for user_id: {user_id}")
            cur.close()
            conn.close()
            return None
        
        company_email = settings_row[0] or 'company@example.com'
        company_inn = settings_row[1] or ''
        company_sno = settings_row[2] or 'usn_income'
        company_payment_address = settings_row[3] or ''
        
        cur.execute("""
            SELECT items, total, payments, operation_type, customer_email, payment_type
            FROM receipts 
            WHERE uuid = %s AND user_id = %s
        """, (uuid_str, user_id))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            return None
        
        items = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        payments = json.loads(row[2]) if isinstance(row[2], str) else row[2]
        payment_type = row[5] or '103'
        
        # Determine document_type based on payment_type
        # payment_type >= 100 means it's a payment link
        try:
            payment_type_int = int(payment_type)
            document_type = 'link' if payment_type_int >= 100 else 'receipt'
            is_payment_link = payment_type_int >= 100
        except (ValueError, TypeError):
            document_type = 'receipt'
            is_payment_link = False
        
        # Get real provider name from Ecomkassa API
        provider_name = f'Провайдер {payment_type}'
        if is_payment_link:
            providers = get_payment_providers(user_id)
            if providers:
                for provider in providers:
                    if str(provider.get('id')) == str(payment_type):
                        provider_desc = provider.get('description', '')
                        # Clean provider description
                        provider_desc = provider_desc.replace('Платёж через счёт ', '')
                        provider_desc = provider_desc.replace('Платёж через эквайринг ', '')
                        provider_desc = provider_desc.replace('Платёж через ', '')
                        provider_desc = provider_desc.replace('"', '')
                        provider_name = provider_desc
                        break
        
        receipt_data = {
            'items': items,
            'total': float(row[1]),
            'payments': payments,
            'operation_type': row[3] or 'Приход',
            'customer_email': row[4],
            'payment_type': payment_type,
            'document_type': document_type,
            'payment_link_enabled': is_payment_link,
            'payment_provider_id': int(payment_type) if is_payment_link else None,
            'payment_provider_name': provider_name if is_payment_link else None,
            'company': {
                'email': company_email,
                'inn': company_inn,
                'sno': company_sno,
                'payment_address': company_payment_address
            },
            'client': {
                'email': row[4] or company_email,
                'phone': None
            }
        }
        
        return receipt_data
    except Exception as e:
        print(f"[ERROR] Failed to get receipt by UUID: {e}")
        return None


def save_last_successful_request(chat_id: int, preview_id: str, preview_data: Dict[str, Any]) -> None:
    '''Save last successful request for /repeat command'''
    try:
        conn = get_db_connection()
        if not conn:
            print("[ERROR] No DB connection in save_last_successful_request")
            return
        cur = conn.cursor()
        
        # Store in database
        cur.execute("""
            INSERT INTO telegram_last_requests (chat_id, preview_id, preview_data, created_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (chat_id) 
            DO UPDATE SET preview_id = %s, preview_data = %s, created_at = NOW()
        """, (chat_id, preview_id, json.dumps(preview_data), preview_id, json.dumps(preview_data)))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"[DEBUG] Saved last request for chat_id={chat_id}")
    except Exception as e:
        print(f"[ERROR] Failed to save last request: {e}")


def get_last_successful_request(chat_id: int) -> Optional[Dict[str, Any]]:
    '''Get last successful request for /repeat command'''
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT preview_id, preview_data 
            FROM telegram_last_requests 
            WHERE chat_id = %s
        """, (chat_id,))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            import uuid
            # Generate new preview_id for repeat
            new_preview_id = str(uuid.uuid4())
            return {
                'preview_id': new_preview_id,
                'preview_data': json.loads(row[1]) if isinstance(row[1], str) else row[1]
            }
        return None
    except Exception as e:
        print(f"[ERROR] Failed to get last request: {e}")
        return None


def show_receipt_preview(bot_token: str, chat_id: int, preview_data: Dict[str, Any], preview_id: str) -> None:
    """Show receipt preview with confirmation buttons"""
    receipt_data = preview_data.get('receipt_data')
    if not receipt_data:
        send_telegram_message(bot_token, chat_id, "❌ Ошибка: данные чека не найдены")
        return
    
    items = receipt_data.get('items', [])
    total = receipt_data.get('total', 0)
    payments = receipt_data.get('payments', [])
    client_data = receipt_data.get('client', {})
    company_data = receipt_data.get('company', {})
    operation_type = receipt_data.get('operation_type', 'sell')
    
    operation_names = {
        'sell': 'Приход',
        'refund': 'Возврат прихода',
        'sell_correction': 'Коррекция прихода',
        'refund_correction': 'Коррекция расхода'
    }
    
    payment_link_enabled = receipt_data.get('payment_link_enabled', False)
    is_payment_link = payment_link_enabled
    
    response_text = "📋 <b>Проверь перед отправкой:</b>\n\n"
    
    # Document type with provider on same line for payment links
    if is_payment_link:
        provider_name = receipt_data.get('payment_provider_name', 'Не выбран')
        response_text += f"<b>Тип документа:</b> 🔗 Платежная ссылка Провайдер: {provider_name}\n"
    else:
        response_text += f"<b>Тип документа:</b> 🧾 Чек\n"
    
    response_text += f"<b>Тип операции:</b> {operation_names.get(operation_type, operation_type)}\n\n"
    
    # Company info (SNO and payment address) IMMEDIATELY after operation type
    sno = company_data.get('sno', 'usn_income')
    payment_address = company_data.get('payment_address', '')
    
    sno_names = {
        'usn_income': 'УСН доход',
        'usn_income_outcome': 'УСН доход-расход',
        'osn': 'ОСНО',
        'esn': 'ЕСХН',
        'patent': 'Патент'
    }
    
    response_text += f"<b>💼 СНО:</b> {sno_names.get(sno, sno)}\n"
    if payment_address:
        response_text += f"<b>📍 Адрес расчетов:</b> {payment_address}\n"
    
    response_text += f"<b>📧 Email клиента:</b> {client_data.get('email', 'Не указан')}\n"
    
    response_text += "\n<b>Товары/Услуги:</b>\n"
    
    # VAT names
    vat_names = {
        'none': 'Без НДС',
        'vat0': 'НДС 0%',
        'vat10': 'НДС 10%',
        'vat20': 'НДС 20%'
    }
    
    # Payment object names
    object_names = {
        'commodity': 'Товар',
        'service': 'Услуга',
        'excise': 'Подакцизный товар',
        'job': 'Работа'
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
    
    for idx, item in enumerate(items, 1):
        name = item.get('name', 'Товар')
        price = item.get('price', 0)
        qty = item.get('quantity', 1)
        measure = item.get('measure', 'шт')
        vat = item.get('vat', 'none')
        payment_object = item.get('payment_object', 'commodity')
        payment_method = item.get('payment_method', 'full_payment')
        
        response_text += f"\n<b>{idx}. {name}</b>\n"
        response_text += f"   Цена: {price}₽ × {qty} {measure}\n"
        response_text += f"   НДС: {vat_names.get(vat, vat)}\n"
        response_text += f"   Предмет: {object_names.get(payment_object, payment_object)}\n"
        response_text += f"   Способ: {method_names.get(payment_method, payment_method)}\n"
    
    response_text += f"\n<b>💰 Итого:</b> {total}₽\n\n"
    
    # Payment details
    if is_payment_link:
        # For payment links, payment method is always "Безналичный" (from provider)
        response_text += f"<b>Способ оплаты:</b> 💳 Безналичный\n"
    elif payments and len(payments) > 1:
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
    
    # CRITICAL: Check balance between items total and payments total
    # Calculate items total
    items_total = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
    # Calculate payments total
    payments_total = sum(payment.get('sum', 0) for payment in payments)
    
    # Check if balanced (with 0.01 tolerance for float precision)
    difference = round(items_total - payments_total, 2)
    
    if abs(difference) > 0.01:
        if difference > 0:
            # Items cost more than paid - client needs to pay more
            response_text += f"\n⚠️ <b>Недоплата:</b> {abs(difference)}₽\n"
            response_text += f"<i>Клиент должен доплатить {abs(difference)}₽</i>\n"
        else:
            # Paid more than items cost - need to return money
            response_text += f"\n⚠️ <b>Переплата:</b> {abs(difference)}₽\n"
            response_text += f"<i>Нужно вернуть клиенту {abs(difference)}₽</i>\n"
    
    buttons = [
        [{"text": "✅ Отправить запрос", "callback_data": f"confirm_{preview_id}"}],
        [{"text": "✏️ Изменить", "callback_data": f"edit_{preview_id}"}],
        [{"text": "❌ Отменить", "callback_data": f"cancel_{preview_id}"}]
    ]
    
    send_telegram_message_with_buttons(bot_token, chat_id, response_text, buttons)


def show_updated_preview(bot_token: str, chat_id: int, preview_id: str, user_id: str) -> None:
    """Show updated preview after editing"""
    preview_data = get_preview_data(preview_id)
    if not preview_data:
        send_telegram_message(bot_token, chat_id, "❌ Ошибка: данные не найдены")
        return
    
    # Use stored receipt_data directly (already updated)
    receipt_data = preview_data.get('receipt_data')
    if not receipt_data:
        send_telegram_message(bot_token, chat_id, "❌ Ошибка: данные чека не найдены")
        return
    items = receipt_data.get('items', [])
    total = receipt_data.get('total', 0)
    payments = receipt_data.get('payments', [])
    client_data = receipt_data.get('client', {})
    operation_type = receipt_data.get('operation_type', 'sell')
    
    # Get saved payment type if exists
    payment_type_override = get_preview_payment_type(preview_id)
    if payment_type_override:
        payments = [{'type': payment_type_override, 'sum': total}]
    
    operation_names = {
        'sell': '🛒 Приход (продажа)',
        'refund': '↩️ Возврат прихода',
        'sell_correction': '📝 Коррекция прихода',
        'refund_correction': '📝 Коррекция расхода'
    }
    
    # CRITICAL: Detect document type from receipt_data
    payment_link_enabled = receipt_data.get('payment_link_enabled', False)
    document_type_text = "🔗 Платежная ссылка" if payment_link_enabled else "🧾 Чек"
    
    response_text = "📋 <b>Проверь перед отправкой:</b>\n\n"
    response_text += f"<b>Тип документа:</b> {document_type_text}\n"
    
    # CRITICAL: Show provider only for payment links
    if payment_link_enabled:
        provider_name = receipt_data.get('payment_provider_name', 'Не выбран')
        response_text += f"<b>💳 Провайдер:</b> {provider_name}\n"
    
    response_text += f"<b>Тип операции:</b> {operation_names.get(operation_type, operation_type)}\n\n"
    
    response_text += "<b>Товары/Услуги:</b>\n"
    for idx, item in enumerate(items, 1):
        name = item.get('name', 'Товар')
        price = item.get('price', 0)
        qty = item.get('quantity', 1)
        measure = item.get('measure', 'шт')
        vat = item.get('vat', 'none')
        payment_method = item.get('payment_method', 'full_payment')
        payment_object = item.get('payment_object', 'commodity')
        
        vat_names = {'none': 'Без НДС', 'vat0': 'НДС 0%', 'vat10': 'НДС 10%', 'vat20': 'НДС 20%'}
        method_names = {
            'full_payment': 'Полный расчёт',
            'prepayment': 'Предоплата',
            'advance': 'Аванс',
            'full_prepayment': 'Предоплата 100%',
            'partial_payment': 'Частичный расчёт',
            'credit': 'Кредит',
            'credit_payment': 'Оплата кредита'
        }
        object_names = {'commodity': 'Товар', 'service': 'Услуга', 'excise': 'Подакцизный товар', 'job': 'Работа'}
        
        response_text += f"\n<b>{idx}. {name}</b>\n"
        response_text += f"   Цена: {price}₽ × {qty} {measure}\n"
        response_text += f"   НДС: {vat_names.get(vat, vat)}\n"
        response_text += f"   Предмет: {object_names.get(payment_object, payment_object)}\n"
        response_text += f"   Способ: {method_names.get(payment_method, payment_method)}\n"
    
    response_text += f"\n<b>💰 Итого:</b> {total}₽\n\n"
    
    # Check if payment link is enabled
    payment_link_enabled = receipt_data.get('payment_link_enabled', False)
    
    if payment_link_enabled:
        # Show payment link info
        provider_name = receipt_data.get('payment_provider_name', 'Не указан')
        response_text += f"<b>🔗 Способ оплаты:</b> Ссылка на оплату ({provider_name})\n"
    elif payments and len(payments) > 1:
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
    
    response_text += f"\n<b>📧 Email клиента:</b> {client_data.get('email', 'Не указан')}\n"
    
    client_phone = client_data.get('phone')
    if client_phone:
        response_text += f"<b>📱 Телефон:</b> {client_phone}\n"
    
    # Company info (SNO and payment address)
    company_data_preview = receipt_data.get('company', {})
    sno_preview = company_data_preview.get('sno', 'usn_income')
    payment_address_preview = company_data_preview.get('payment_address', '')
    
    sno_names_preview = {
        'usn_income': 'УСН доход',
        'usn_income_outcome': 'УСН доход-расход',
        'osn': 'ОСНО',
        'esn': 'ЕСХН',
        'patent': 'Патент'
    }
    
    response_text += f"\n<b>💼 СНО:</b> {sno_names_preview.get(sno_preview, sno_preview)}\n"
    if payment_address_preview:
        response_text += f"<b>📍 Адрес расчетов:</b> {payment_address_preview}\n"
    
    # CRITICAL: Check balance between items total and payments total
    # Calculate items total
    items_total = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
    # Calculate payments total
    payments_total = sum(payment.get('sum', 0) for payment in payments)
    
    # Check if balanced (with 0.01 tolerance for float precision)
    difference = round(items_total - payments_total, 2)
    
    if abs(difference) > 0.01:
        if difference > 0:
            # Items cost more than paid - client needs to pay more
            response_text += f"\n⚠️ <b>Недоплата:</b> {abs(difference)}₽\n"
            response_text += f"<i>Клиент должен доплатить {abs(difference)}₽</i>\n"
        else:
            # Paid more than items cost - need to return money
            response_text += f"\n⚠️ <b>Переплата:</b> {abs(difference)}₽\n"
            response_text += f"<i>Нужно вернуть клиенту {abs(difference)}₽</i>\n"
    
    send_telegram_message_with_buttons(
        bot_token,
        chat_id,
        response_text,
        [
            [{"text": "✅ Отправить чек", "callback_data": f"confirm_{preview_id}"}],
            [{"text": "✏️ Изменить", "callback_data": f"edit_{preview_id}"}],
            [{"text": "❌ Отменить", "callback_data": f"cancel_{preview_id}"}]
        ]
    )


def get_preview_payment_type(preview_id: str) -> Optional[str]:
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return None
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute(
            "SELECT payment_type FROM telegram_previews WHERE preview_id = %s",
            (preview_id,)
        )
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result and result[0]:
            return result[0]
        
        return None
    except Exception as e:
        print(f"[ERROR] Failed to get payment type: {e}")
        return None


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


def get_ecomkassa_token(login: str, password: str) -> Optional[str]:
    '''Get Ecomkassa API token'''
    auth_url = 'https://app.ecomkassa.ru/fiscalorder/v5/getToken'
    
    payload = {
        'login': login,
        'pass': password
    }
    
    try:
        req = urllib.request.Request(
            auth_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json; charset=utf-8'},
            method='POST'
        )
        
        print(f"[DEBUG] Getting token for login: {login[:3]}***")
        with urllib.request.urlopen(req, timeout=10) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            print(f"[DEBUG] Token response code: {response_data.get('code')}")
            if response_data.get('code') == 0:
                token = response_data.get('token')
                print(f"[DEBUG] Token received: {token[:50] if token else 'None'}...")
                return token
            else:
                print(f"[DEBUG] Token error: {response_data.get('text')}")
                return None
    
    except Exception as e:
        print(f"[DEBUG] Exception getting token: {str(e)}")
        return None


def get_payment_providers(user_id: str) -> Optional[list]:
    '''Load payment providers from Ecomkassa API'''
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return None
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute(
            "SELECT ecomkassa_login, ecomkassa_password, group_code FROM user_settings WHERE user_id = %s LIMIT 1",
            (user_id,)
        )
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            print(f"[ERROR] No user settings found for user_id: {user_id}")
            return None
        
        login, password, group_code = row
        
        if not (login and password and group_code):
            print(f"[ERROR] Missing ecomkassa credentials for user_id: {user_id}")
            return None
        
        token = get_ecomkassa_token(login, password)
        if not token:
            print(f"[ERROR] Failed to get ecomkassa token")
            return None
        
        api_url = f'https://app.ecomkassa.ru/fiscalorder/v4/{group_code}/paymentTypes'
        
        req = urllib.request.Request(
            api_url,
            headers={
                'Content-Type': 'application/json',
                'Token': token
            },
            method='GET'
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            providers = json.loads(response.read().decode('utf-8'))
            print(f"[DEBUG] Loaded {len(providers)} payment providers")
            return providers
    
    except Exception as e:
        print(f"[ERROR] Failed to load payment providers: {e}")
        return None


def handle_voice_message(message: dict, bot_token: str) -> Dict[str, Any]:
    '''
    Download voice message and transcribe using Yandex SpeechKit
    Returns: {'text': transcribed_text} or {'error': message}
    '''
    voice = message.get('voice', {})
    file_id = voice.get('file_id')
    
    if not file_id:
        return {'error': 'Voice file_id not found'}
    
    # Check if Yandex SpeechKit is enabled in admin settings and get API key from DB
    dsn = os.environ.get('DATABASE_URL')
    speechkit_enabled = False
    api_key = None
    
    if dsn:
        try:
            conn = psycopg2.connect(dsn)
            cur = conn.cursor()
            cur.execute("SELECT active_provider, yandex_speechkit_key FROM ai_settings ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row and row[0] == 'yandex_speechkit':
                speechkit_enabled = True
                api_key = row[1] if len(row) > 1 else None
            cur.close()
            conn.close()
        except Exception as e:
            print(f"[ERROR] Failed to check SpeechKit status: {e}")
    
    if not speechkit_enabled:
        return {'error': 'Распознавание речи не настроено. Включите Yandex SpeechKit в админке.'}
    
    if not api_key:
        return {'error': 'SpeechKit API key not configured'}
    
    # Get file path from Telegram
    try:
        file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        file_info_req = urllib.request.Request(file_info_url)
        file_info_resp = urllib.request.urlopen(file_info_req, timeout=10)
        file_info_data = json.loads(file_info_resp.read().decode('utf-8'))
        
        if not file_info_data.get('ok'):
            return {'error': 'Failed to get file info from Telegram'}
        
        file_path = file_info_data['result']['file_path']
        file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        
        # Download voice file
        file_req = urllib.request.Request(file_url)
        file_resp = urllib.request.urlopen(file_req, timeout=30)
        voice_data = file_resp.read()
        
        # Call Yandex SpeechKit API
        speechkit_url = 'https://stt.api.cloud.yandex.net/speech/v1/stt:recognize'
        speechkit_req = urllib.request.Request(
            f"{speechkit_url}?lang=ru-RU&format=oggopus",
            data=voice_data,
            headers={
                'Authorization': f'Api-Key {api_key}'
            },
            method='POST'
        )
        
        speechkit_resp = urllib.request.urlopen(speechkit_req, timeout=60)
        speechkit_data = json.loads(speechkit_resp.read().decode('utf-8'))
        
        transcribed_text = speechkit_data.get('result', '').strip()
        
        if not transcribed_text:
            return {'error': 'Could not transcribe voice message'}
        
        return {'text': transcribed_text}
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        print(f"[ERROR] Voice transcription failed: {e.code} {error_body}")
        return {'error': f'HTTP error {e.code}'}
    except Exception as e:
        print(f"[ERROR] Voice handling failed: {e}")
        return {'error': f'Failed to process voice: {str(e)}'}


def update_preview_payment(preview_id: str, payment_type: str) -> bool:
    """Update payment type in telegram_previews receipt_data"""
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return False
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute(
            "SELECT receipt_data FROM telegram_previews WHERE preview_id = %s",
            (preview_id,)
        )
        result = cur.fetchone()
        
        if not result or not result[0]:
            print(f"[ERROR] No receipt_data found for preview_id: {preview_id}")
            cur.close()
            conn.close()
            return False
        
        receipt_data = result[0]
        
        if 'payments' in receipt_data and len(receipt_data['payments']) > 0:
            receipt_data['payments'][0]['type'] = payment_type
            print(f"[DEBUG] Updated payment type to {payment_type}")
        
        cur.execute(
            "UPDATE telegram_previews SET receipt_data = %s WHERE preview_id = %s",
            (json.dumps(receipt_data), preview_id)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[SUCCESS] Updated payment type for preview {preview_id}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to update preview payment: {str(e)}")
        return False


def update_preview_payment_provider(preview_id: str, provider_id: str, provider_name: str = '') -> bool:
    """Update payment provider in telegram_previews receipt_data"""
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return False
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute(
            "SELECT receipt_data FROM telegram_previews WHERE preview_id = %s",
            (preview_id,)
        )
        result = cur.fetchone()
        
        if not result or not result[0]:
            print(f"[ERROR] No receipt_data found for preview_id: {preview_id}")
            cur.close()
            conn.close()
            return False
        
        receipt_data = result[0]
        
        # CRITICAL: Payment link uses provider ID in payments[0].type
        # Example: Sberbank = 103, YuKassa = 102, etc.
        # This is sent directly to Ecomkassa API as payment type
        if 'payments' in receipt_data and len(receipt_data['payments']) > 0:
            receipt_data['payments'][0]['type'] = int(provider_id)  # Provider ID as payment type
            print(f"[DEBUG] Set payment provider ID {provider_id} as payment type for payment link")
        
        receipt_data['payment_link_enabled'] = True
        receipt_data['payment_provider_id'] = int(provider_id)  # Store provider ID separately for display
        receipt_data['payment_provider_name'] = provider_name  # Save provider name for display
        receipt_data['operation_type'] = 'sell'  # Always Продажа for payment link
        print(f"[DEBUG] Set operation_type to 'sell' for payment link")
        
        cur.execute(
            "UPDATE telegram_previews SET receipt_data = %s WHERE preview_id = %s",
            (json.dumps(receipt_data), preview_id)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[SUCCESS] Updated payment provider for preview {preview_id}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to update payment provider: {str(e)}")
        return False


def update_preview_operation_type(preview_id: str, operation_type: str) -> bool:
    """Update operation type in telegram_previews receipt_data"""
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return False
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute(
            "SELECT receipt_data FROM telegram_previews WHERE preview_id = %s",
            (preview_id,)
        )
        result = cur.fetchone()
        
        if not result or not result[0]:
            print(f"[ERROR] No receipt_data found for preview_id: {preview_id}")
            cur.close()
            conn.close()
            return False
        
        receipt_data = result[0]
        
        receipt_data['operation_type'] = operation_type
        print(f"[DEBUG] Updated operation_type to {operation_type}")
        
        cur.execute(
            "UPDATE telegram_previews SET receipt_data = %s WHERE preview_id = %s",
            (json.dumps(receipt_data), preview_id)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[SUCCESS] Updated operation_type for preview {preview_id}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to update preview operation_type: {str(e)}")
        return False


def update_preview_field_value(preview_id: str, field: str, value: str) -> bool:
    """Update a specific field value in telegram_previews receipt_data items or company"""
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        return False
    
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        
        cur.execute(
            "SELECT receipt_data FROM telegram_previews WHERE preview_id = %s",
            (preview_id,)
        )
        result = cur.fetchone()
        
        if not result or not result[0]:
            print(f"[ERROR] No receipt_data found for preview_id: {preview_id}")
            cur.close()
            conn.close()
            return False
        
        receipt_data = result[0]
        
        # Update field based on type
        if field in ['measure', 'vat', 'payment_object', 'payment_method']:
            # These fields are in items
            if receipt_data.get('items') and len(receipt_data['items']) > 0:
                receipt_data['items'][0][field] = value
                print(f"[DEBUG] Updated {field} to {value} in items")
            else:
                print(f"[ERROR] No items found in receipt_data")
                cur.close()
                conn.close()
                return False
        elif field in ['sno', 'payment_address']:
            # These fields are in company
            if 'company' not in receipt_data:
                receipt_data['company'] = {}
            receipt_data['company'][field] = value
            print(f"[DEBUG] Updated {field} to {value} in company")
        else:
            print(f"[ERROR] Unknown field: {field}")
            cur.close()
            conn.close()
            return False
        
        cur.execute(
            "UPDATE telegram_previews SET receipt_data = %s WHERE preview_id = %s",
            (json.dumps(receipt_data), preview_id)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[SUCCESS] Updated {field} for preview {preview_id}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to update preview field {field}: {str(e)}")
        return False
        return {'error': str(e)}