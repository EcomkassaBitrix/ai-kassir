import json
import os
import urllib.request
import urllib.error
import uuid
import re
from typing import Dict, Any, Optional


def get_ai_completion(user_text: str, settings: dict, context: str = '') -> Optional[Dict[str, Any]]:
    '''
    Universal AI completion function supporting multiple providers
    Returns parsed receipt JSON or None if failed
    context: previous incomplete request from user
    Updated: Added service detection rules for psychologist and other professional services
    '''
    active_provider = settings.get('active_ai_provider', 'gigachat')
    
    context_part = f"\n\nКонтекст предыдущего запроса: \"{context}\"\n\nВАЖНО: Если новый запрос содержит только недостающие данные (email, phone), НЕ дублируй товары из контекста. Объедини данные в один чек:\n- Товары берём из контекста (если там есть)\n- Email/phone берём из нового запроса (если указан)\nЕсли новый запрос содержит новые товары - добавь их к существующим." if context else ""
    
    prompt = f"""Ты ИИ кассир, который получает запросы на создание чека текстом или голосовыми сообщениями.

Задача: Преобразуй запрос в JSON, заполняя часть API запроса по документации Ecomkassa (https://ecomkassa.ru/dokumentacija_cheki_12).

Запрос: "{user_text}"{context_part}

ВАЖНО: Запрос может быть голосовым (с ошибками распознавания). Исправляй очевидные опечатки и синонимы:
- "150₽" = "150 рублей" = "150р" = "150 руб" = "полторы сотни"
- "1300.12₽" = "1300,12 рублей" = "тысяча триста рублей двенадцать копеек"
- "ivan@mail.ru" = "иван собака мейл точка ру" = "ivan at mail dot ru"
- Числа: "2000" = "две тысячи" = "2к" = "2 тыщи"

КРИТИЧНО про название товара/услуги (name):
- Название товара - это конкретный товар или услуга, которую продаешь
- Примеры: "мебель на заказ за 1300₽" → name: "мебель на заказ"
- Примеры: "Я продаю стрижку и укладку за 2000" → name: "стрижка и укладка"
- Примеры: "кофе американо 200₽" → name: "кофе американо"
- НЕ включай в название: цену, способ оплаты, email, телефон
- ВАЖНО: Слова "платежная ссылка", "ссылка на оплату", "QR", "эквайринг" - это НЕ товар, а способ оплаты!
- Если в запросе только "платежная ссылка" без товара - верни error: "Укажи товар/услугу для платежной ссылки. Пример: консультация 5000₽ ссылка сбербанк"

Пользователь указывает данные из массивов:
- items (товары/услуги): name, price, quantity, measure, vat, payment_method, payment_object
- payments (способы оплаты): массив объектов с полями type (тип оплаты) и sum (сумма)
- client (данные клиента): email, phone

ВАЖНО про payments:
- По умолчанию один платёж (безналичный на всю сумму)
- Для смешанной оплаты (наличные+безнал, взнос+кредит): несколько платежей
- Типы: "0"=наличные, "1"=безналичный, "2"=предоплата(аванс), "3"=последующая оплата(кредит), "4"=иная форма
- Сумма всех payments ОБЯЗАТЕЛЬНО должна равняться общей стоимости товаров

Примеры смешанной оплаты:
- "500 наличными, остальное картой" → payments: [{{"type":"0","sum":500}}, {{"type":"1","sum":ОСТАТОК}}]
- "первоначальный взнос 500, остальное в кредит" → payments: [{{"type":"1","sum":500}}, {{"type":"3","sum":ОСТАТОК}}]
- "аванс 300, остальное потом" → payments: [{{"type":"2","sum":300}}, {{"type":"3","sum":ОСТАТОК}}]

КРИТИЧНО про обязательные данные:
- price (цена): ОБЯЗАТЕЛЬНА. Если не указана - спрашивай через error
- name (название товара/услуги): ОБЯЗАТЕЛЬНО. НИКОГДА не подставляй "товар", "услуга" - всегда спрашивай через error, что именно продаётся
- email/phone: НЕ обязательны. Если не указаны - можно оставить null (бэкэнд подставит дефолтный email)

ВАЖНО: Если пользователь явно указывает отсутствие email клиента, оставляй client.email = null. Бэкэнд автоматически подставит дефолтный email из настроек.
Варианты фраз: "без почты", "нет почты", "без email", "нет email", "не отправлять чек", "без отправки", "почты нет", "email нет", "на дефолтный email", "на стандартную почту".

Валидацию проверенных данных делай по протоколу Атол онлайн (https://atol.online/upload/iblock/c9e/8j5817ef027cwjsww1b67msvdcpxshax/API_сервиса_АТОЛ%20Онлайн_v5.pdf).

Поля (только корректные значения):
operation_type: sell/sell_refund
payment_object: commodity/service (ВАЖНО: автоматически определяй по контексту!)
vat: none/vat20/vat10 (дефолт none)
measure: шт/услуга
client: email (проверь формат), phone (+7...), МОЖНО null если "без почты"

ВАЖНО про payment_object (предмет расчета):
• service - если это УСЛУГА (действие, работа человека или выполнение чего-либо):
  - Профессиональные услуги: психолог, консультация, коуч, юрист, адвокат, бухгалтер, нотариус
  - Медицинские услуги: массаж, процедура, лечение, диагностика, анализ
  - Красота: стрижка, укладка, маникюр, педикюр, макияж, окрашивание, наращивание
  - Образовательные: урок, занятие, курс, тренинг, вебинар, мастер-класс
  - Бытовые: уборка, ремонт, настройка, установка, доставка, транспорт, такси
  - Креативные: дизайн, разработка, фотосессия, видеосъёмка, монтаж
  - Спорт: тренировка, фитнес, йога, массаж
  - Аренда: помещения, оборудования, транспорта
• commodity - если это ТОВАР (физический предмет, который продается):
  - Еда и напитки: кофе, чай, обед, пирожок, торт, продукты
  - Техника: телефон, ноутбук, наушники, зарядка
  - Одежда: футболка, джинсы, обувь, аксессуары
  - Мебель: шкаф, стол, стул, диван
  - Другие физические товары

Если неясно - смотри на контекст: "психолог" = услуга, "кофе" = товар, "мебель на заказ" = товар

ВАЖНО про payment_method (признак способа расчета по ФФД 1.2):
• full_prepayment – предоплата 100%. Полная предоплата до передачи товара
• prepayment – предоплата (частичная). Частичная предоплата до передачи товара
• advance – аванс
• full_payment – полный расчет. Полная оплата (в т.ч. с учетом аванса) в момент передачи товара
• partial_payment – частичный расчет и кредит. Частичная оплата при передаче + последующая оплата в кредит
• credit – передача в кредит. Передача товара без оплаты с последующей оплатой в кредит
• credit_payment – оплата кредита. Оплата товара после передачи (погашение кредита)

Как определить payment_method для ТИПИЧНЫХ сценариев:
1. Обычная продажа (оплата сразу полностью): full_payment
2. Частичная оплата + кредит (взнос + type="3"): partial_payment
3. Только кредит без взноса (только type="3"): credit
4. Предоплата 100%: full_prepayment
5. Аванс: advance

ПО УМОЛЧАНИЮ используй full_payment для обычных продаж

Часть данных подставит бэкэнд (group_code, inn, sno, default_vat, company_email, payment_address), так как он связан с настройками который вводит пользователя.

Успешный формат (простая оплата):
{{"operation_type":"sell","items":[{{"name":"Товар","price":100,"quantity":1,"measure":"шт","vat":"none","payment_method":"full_payment","payment_object":"commodity"}}],"client":{{"email":"user@mail.ru","phone":null}},"payments":[{{"type":"1","sum":100}}]}}

Формат БЕЗ ПОЧТЫ (бэкэнд подставит дефолтный email):
{{"operation_type":"sell","items":[{{"name":"Товар","price":100,"quantity":1,"measure":"шт","vat":"none","payment_method":"full_payment","payment_object":"commodity"}}],"client":{{"email":null,"phone":null}},"payments":[{{"type":"1","sum":100}}]}}

Если НЕ ХВАТАЕТ ДАННЫХ - ОБЯЗАТЕЛЬНО верни error с детальным объяснением:
{{"error":"Не хватает данных для чека: укажи цену товара/услуги. Email можно не указывать (будет использован дефолтный). Пример: изготовление шкафа 25000₽"}}

Примеры запросов:
- "кофе 200₽ без почты" → {{"operation_type":"sell","items":[{{"name":"кофе","price":200,"quantity":1,"measure":"шт","vat":"none","payment_method":"full_payment","payment_object":"commodity"}}],"client":{{"email":null,"phone":null}},"payments":[{{"type":"1","sum":200}}]}}
- "психолог 27 рубля без почты" → {{"operation_type":"sell","items":[{{"name":"психолог","price":27,"quantity":1,"measure":"услуга","vat":"none","payment_method":"full_payment","payment_object":"service"}}],"client":{{"email":null,"phone":null}},"payments":[{{"type":"1","sum":27}}]}}
- "услуга 1500₽ не отправлять чек" → {{"operation_type":"sell","items":[{{"name":"услуга","price":1500,"quantity":1,"measure":"услуга","vat":"none","payment_method":"full_payment","payment_object":"service"}}],"client":{{"email":null,"phone":null}},"payments":[{{"type":"1","sum":1500}}]}}
- "консультация юриста 3000₽" → {{"operation_type":"sell","items":[{{"name":"консультация юриста","price":3000,"quantity":1,"measure":"услуга","vat":"none","payment_method":"full_payment","payment_object":"service"}}],"client":{{"email":null,"phone":null}},"payments":[{{"type":"1","sum":3000}}]}}
- "Я продаю мебель на заказ за 1300.12 в кредит первоначальный взнос 500" → {{"operation_type":"sell","items":[{{"name":"мебель на заказ","price":1300.12,"quantity":1,"measure":"шт","vat":"none","payment_method":"partial_payment","payment_object":"commodity"}}],"client":{{"email":null,"phone":null}},"payments":[{{"type":"1","sum":500}},{{"type":"3","sum":800.12}}]}}
- "товар 1000₽, 600 наличными остальное картой" → {{"operation_type":"sell","items":[{{"name":"товар","price":1000,"quantity":1,"measure":"шт","vat":"none","payment_method":"full_payment","payment_object":"commodity"}}],"client":{{"email":null,"phone":null}},"payments":[{{"type":"0","sum":600}},{{"type":"1","sum":400}}]}}
- "стрижка и укладка 2500₽" → {{"operation_type":"sell","items":[{{"name":"стрижка и укладка","price":2500,"quantity":1,"measure":"услуга","vat":"none","payment_method":"full_payment","payment_object":"service"}}],"client":{{"email":null,"phone":null}},"payments":[{{"type":"1","sum":2500}}]}}
- "кофе" → {{"error":"Укажи цену. Email необязателен (будет дефолтный). Пример: кофе 200₽"}}
- "стрижка test@mail.ru" → {{"error":"Укажи цену услуги. Пример: стрижка 1500₽ test@mail.ru"}}
- "изготовление шкафа" → {{"error":"Укажи цену. Пример: изготовление шкафа 25000₽"}}
- "создай чек 50 без почты" → {{"error":"Что продаёшь за 50₽? Укажи название товара/услуги. Пример: кофе 50₽ без почты"}}
- "чек на 100₽" → {{"error":"Что продаёшь за 100₽? Укажи товар или услугу. Пример: консультация 100₽"}}
- "50 рублей без email" → {{"error":"Укажи название товара/услуги. Что продаёшь за 50₽? Пример: обед 50₽"}}
- "Платежная ссылка на 1 рубль test@mail.ru" → {{"error":"Укажи товар/услугу для платежной ссылки. Что продаешь за 1 рубль? Пример: консультация 1₽ ссылка сбербанк"}}
- "ссылка сбербанк 500₽" → {{"error":"Что продаешь за 500₽? Укажи товар/услугу. Пример: подписка 500₽ ссылка сбербанк"}}

JSON:"""
    
    # Updated 2025-11-27: Added detailed rules for service vs commodity detection
    print(f"[DEBUG] Using AI provider: {active_provider}")
    
    if active_provider == 'gigachat':
        return call_gigachat(prompt, settings)
    elif active_provider == 'yandexgpt':
        return call_yandexgpt(prompt, settings)
    elif active_provider == 'gptunnel_chatgpt':
        return call_gptunnel(prompt, settings, 'gpt-4o')
    elif active_provider == 'gptunnel_claude':
        return call_gptunnel(prompt, settings, 'claude-3.5-sonnet')
    else:
        print(f"[WARN] Unknown provider {active_provider}, falling back to GigaChat")
        return call_gigachat(prompt, settings)


def call_gigachat(prompt: str, settings: dict) -> Optional[Dict[str, Any]]:
    '''Call GigaChat API'''
    import requests
    
    auth_key = settings.get('gigachat_auth_key') or os.environ.get('GIGACHAT_AUTH_KEY', '')
    if not auth_key:
        return None
    
    access_token = get_gigachat_token(auth_key)
    if not access_token:
        return None
    
    chat_url = 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': 'GigaChat',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.1,
        'max_tokens': 1000
    }
    
    try:
        response = requests.post(chat_url, headers=headers, json=payload, verify=False, timeout=5)
        result = response.json()
        ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        return extract_json_from_text(ai_response)
    except Exception as e:
        print(f"[ERROR] GigaChat failed: {e}")
        return None


def call_yandexgpt(prompt: str, settings: dict) -> Optional[Dict[str, Any]]:
    '''Call YandexGPT API'''
    import requests
    
    api_key = settings.get('yandexgpt_api_key', '')
    folder_id = settings.get('yandexgpt_folder_id', '')
    if not api_key or not folder_id:
        return None
    
    url = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'
    headers = {
        'Authorization': f'Api-Key {api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'modelUri': f'gpt://{folder_id}/yandexgpt-lite',
        'completionOptions': {
            'temperature': 0.1,
            'maxTokens': 1000
        },
        'messages': [{'role': 'user', 'text': prompt}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        result = response.json()
        ai_response = result.get('result', {}).get('alternatives', [{}])[0].get('message', {}).get('text', '')
        return extract_json_from_text(ai_response)
    except Exception as e:
        print(f"[ERROR] YandexGPT failed: {e}")
        return None


def call_gptunnel(prompt: str, settings: dict, model: str) -> Optional[Dict[str, Any]]:
    '''Call GPT Tunnel API (ChatGPT or Claude)'''
    import requests
    
    api_key = settings.get('gptunnel_api_key', '')
    if not api_key:
        return None
    
    url = 'https://gptunnel.ru/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.1,
        'max_tokens': 1000
    }
    
    try:
        print(f"[DEBUG] Calling GPT Tunnel API: {url}, model: {model}")
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"[DEBUG] GPT Tunnel response status: {response.status_code}")
        result = response.json()
        print(f"[DEBUG] GPT Tunnel response: {result}")
        ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        print(f"[DEBUG] AI response text: {ai_response[:200]}")
        return extract_json_from_text(ai_response)
    except Exception as e:
        print(f"[ERROR] GPT Tunnel ({model}) failed: {e}")
        return None


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    '''Extract and parse JSON from AI response text'''
    import re
    
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if not json_match:
        return None
    
    try:
        json_str = json_match.group(0).replace('\n', ' ').replace('\r', ' ')
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def load_user_settings_from_db(user_id: str) -> Optional[Dict[str, Any]]:
    '''Load user settings from database by user_id'''
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return None
    
    import psycopg2
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        cur.execute(
            "SELECT ecomkassa_login, ecomkassa_password, group_code, company_email, inn, sno, payment_address, default_vat "
            "FROM user_settings WHERE user_id = %s LIMIT 1",
            (user_id,)
        )
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return {
                'ecomkassa_login': row[0] or '',
                'ecomkassa_password': row[1] or '',
                'group_code': row[2] or '',
                'company_email': row[3] or '',
                'inn': row[4] or '',
                'sno': row[5] or 'usn_income',
                'payment_address': row[6] or '',
                'default_vat': row[7] or 'none'
            }
        
        return None
    except Exception as e:
        print(f"[ERROR] Failed to load user settings: {e}")
        return None


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    '''
    Business: Process natural language receipt requests and create receipt via ecomkassa API
    Args: event - dict with httpMethod, body, queryStringParameters
          context - object with attributes: request_id, function_name
    Returns: HTTP response dict with receipt data
    '''
    method: str = event.get('httpMethod', 'GET')
    
    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-User-Id',
                'Access-Control-Max-Age': '86400'
            },
            'body': ''
        }
    
    if method != 'POST':
        return {
            'statusCode': 405,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Method not allowed'})
        }
    
    headers = event.get('headers', {})
    user_id: str = headers.get('X-User-Id', headers.get('x-user-id', ''))
    
    body_data = json.loads(event.get('body', '{}'))
    user_message: str = body_data.get('message', '')
    operation_type: str = body_data.get('operation_type', '')
    preview_only: bool = body_data.get('preview_only', False)
    document_type: str = body_data.get('document_type', 'receipt')  # CRITICAL: 'receipt' or 'link'
    auto_selected_provider: dict = body_data.get('auto_selected_provider')  # CRITICAL: Auto-detected provider
    detected_provider_keyword: str = body_data.get('detected_provider_keyword', '')  # Keyword found in text
    settings: dict = body_data.get('settings', {})
    previous_receipt: dict = body_data.get('previous_receipt', {})
    edited_data: dict = body_data.get('edited_data')
    context_message: str = body_data.get('context_message', '')
    
    print(f"[DEBUG] document_type: {document_type}, preview_only: {preview_only}")
    print(f"[DEBUG] auto_selected_provider: {auto_selected_provider}, detected_keyword: {detected_provider_keyword}")
    
    # Load user settings from database if user_id is provided
    if user_id:
        print(f"[DEBUG] Loading settings for user_id: {user_id}")
        user_settings = load_user_settings_from_db(user_id)
        if user_settings:
            print(f"[DEBUG] User settings loaded: ecomkassa_login={user_settings.get('ecomkassa_login')}, group_code={user_settings.get('group_code')}")
            # Merge user settings with provided settings (user settings take priority)
            settings = {**settings, **user_settings}
        else:
            print(f"[DEBUG] No user settings found for user_id: {user_id}")
    
    if not user_message:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Message is required'})
        }
    
    text_lower = user_message.lower().strip()
    
    context_message = settings.get('context_message', '')
    has_context = bool(context_message)
    
    irrelevant_keywords = [
        'привет', 'здравствуй', 'добрый', 'доброе', 'hello', 'hi', 'hey',
        'расскажи', 'что такое', 'как дела', 'анекдот', 'пошути', 
        'кто ты', 'спасибо', 'благодарю', 'помоги', 'помощь',
        'шутка', 'история', 'сказка', 'стих', 'стоп', 'хватит', 'стой',
        'привет', 'пока', 'досвидания', 'хай', 'хелло'
    ]
    
    has_receipt_keywords = any(keyword in text_lower for keyword in [
        'чек', 'товар', 'услуга', 'продаж', 'возврат', 'корр', 
        'руб', '₽', 'email', '@', 'цена', 'сумма', 'отправ', 'созда',
        'копи', 'повтор', 'дубл', 'еще раз', 'ещё раз'
    ])
    
    has_copy_request = bool(re.search(r'\d{8,}', user_message)) and any(keyword in text_lower for keyword in ['копи', 'повтор', 'дубл', 'еще', 'ещё'])
    
    if not has_receipt_keywords and not has_context and not has_copy_request:
        for keyword in irrelevant_keywords:
            if keyword in text_lower:
                print(f"[DEBUG] Irrelevant request blocked: '{user_message}' contains '{keyword}'")
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'success': False,
                        'message': 'Привет! 👋 Я ИИ-кассир. Помогаю создавать чеки.\n\nНапример:\n• "Кофе 200₽"\n• "Стрижка 1500₽ test@mail.ru"\n• "Продал телефон 15000"'
                    })
                }
        
        if len(text_lower) < 10:
            print(f"[DEBUG] Too short message without receipt keywords and no context: '{user_message}'")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': '❌ Я ИИ-кассир и помогаю только с созданием чеков. Укажи товар/услугу, цену и email клиента для создания чека.'
                })
            }
    
    has_ecomkassa = (settings.get('ecomkassa_login') or settings.get('username')) and \
                    (settings.get('ecomkassa_password') or settings.get('password')) and \
                    settings.get('group_code')
    
    # Get AI settings from database (admin-level settings)
    database_url = os.environ.get('DATABASE_URL')
    active_ai_provider = ''
    has_admin_ai = False
    
    if database_url:
        try:
            import psycopg2
            conn = psycopg2.connect(database_url)
            cur = conn.cursor()
            # CRITICAL: Use text_provider and gptunnel_api_key from DB (after migration V0014)
            cur.execute("SELECT text_provider, selected_model, gptunnel_api_key FROM ai_settings ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row and row[0]:
                active_ai_provider = row[0]
                selected_model = row[1] if len(row) > 1 else None
                gptunnel_api_key = row[2] if len(row) > 2 else None
                
                # GPTunnel uses API key from database
                if active_ai_provider == 'gptunnel_chatgpt':
                    if gptunnel_api_key:
                        has_admin_ai = True
                        settings['gptunnel_api_key'] = gptunnel_api_key
                        settings['active_ai_provider'] = 'gptunnel_chatgpt'
                        if selected_model:
                            settings['gptunnel_model'] = selected_model
                # Legacy providers (GigaChat, YandexGPT) - still use environment
                elif active_ai_provider == 'gigachat':
                    gigachat_key = os.environ.get('GIGACHAT_AUTH_KEY')
                    if gigachat_key:
                        has_admin_ai = True
                        settings['gigachat_auth_key'] = gigachat_key
                        settings['active_ai_provider'] = 'gigachat'
                elif active_ai_provider == 'yandexgpt':
                    yandexgpt_key = os.environ.get('YANDEXGPT_API_KEY')
                    if yandexgpt_key:
                        has_admin_ai = True
                        settings['yandexgpt_api_key'] = yandexgpt_key
                        settings['yandexgpt_folder_id'] = os.environ.get('YANDEXGPT_FOLDER_ID', '')
                        settings['active_ai_provider'] = 'yandexgpt'
            cur.close()
            conn.close()
        except Exception as e:
            print(f"[WARNING] Failed to get admin AI settings: {e}")
    
    if not has_ecomkassa and not preview_only:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Настройки ЕкомКасса не заполнены',
                'message': 'Перейди в Настройки и заполни: логин, пароль и код группы касс ЕкомКасса',
                'missing_integration': 'ecomkassa'
            })
        }
    
    if (not has_admin_ai or not active_ai_provider) and not preview_only:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'AI провайдер не подключен',
                'message': 'Перейди в Настройки и подключи AI провайдера (GigaChat, YandexGPT или GPT Tunnel)',
                'missing_integration': 'ai'
            })
        }
    
    # CRITICAL: Check edited_data FIRST before detecting bulk commands
    # If edited_data exists, user already confirmed the preview - skip command detection
    if edited_data:
        print(f"[DEBUG] Using edited_data: {json.dumps(edited_data, ensure_ascii=False)[:500]}")
        print(f"[DEBUG] edited_data has bulk_count: {edited_data.get('bulk_count')}")
        print(f"[DEBUG] edited_data has original_uuid: {edited_data.get('original_uuid')}")
        parsed_receipt = edited_data
        operation_type = edited_data.get('operation_type', operation_type)
        
        # Apply price recalculation for edited_data too
        if parsed_receipt.get('payments'):
            total_from_payments = sum(payment.get('sum', 0) for payment in parsed_receipt['payments'])
            if total_from_payments > 0:
                items_total = sum(item.get('price', 0) * item.get('quantity', 1) for item in parsed_receipt.get('items', []))
                if abs(items_total - total_from_payments) > 0.01:
                    print(f"[DEBUG] [EDITED_DATA] Recalculating prices: items_total={items_total}, payments_total={total_from_payments}")
                    if len(parsed_receipt.get('items', [])) == 1:
                        parsed_receipt['items'][0]['price'] = total_from_payments / parsed_receipt['items'][0].get('quantity', 1)
                        print(f"[DEBUG] [EDITED_DATA] Updated single item price to {parsed_receipt['items'][0]['price']}")
                parsed_receipt['total'] = total_from_payments
        # Skip to email check and receipt creation - do NOT re-parse bulk commands
    else:
        # Only detect bulk commands if NO edited_data (initial request)
        # First, try AI-based bulk detection
        bulk_repeat = detect_bulk_with_ai(user_message, settings)
        if not bulk_repeat:
            # Fallback to regex-based detection
            bulk_repeat = detect_bulk_repeat_command(user_message)
        
        if bulk_repeat:
            count, uuid = bulk_repeat
            if count > 50:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': f'Слишком много копий: {count}. Максимум 50 чеков за раз'
                    })
                }
            
            existing_receipt = get_receipt_from_db(uuid)
            print(f"[DEBUG] Retrieved receipt from DB: {existing_receipt is not None}")
            if not existing_receipt:
                print(f"[DEBUG] Receipt {uuid} not found in database")
                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': f'Чек с UUID {uuid} не найден в истории'
                    })
                }
            print(f"[DEBUG] Receipt found! Items: {existing_receipt.get('items')}")
            
            # Use customer email from receipt, fallback to company email if empty
            customer_email = existing_receipt.get('customer_email', '').strip()
            if not customer_email:
                customer_email = settings.get('company_email', 'company@example.com')
            
            parsed_receipt = {
                'items': existing_receipt['items'],
                'total': existing_receipt['total'],
                'payment_type': existing_receipt.get('payment_type', 'card'),
                'payments': existing_receipt.get('payments', [{
                    'type': '0' if existing_receipt.get('payment_type') == 'cash' else '1',
                    'sum': existing_receipt['total']
                }]),
                'client': {
                    'email': customer_email,
                    'phone': existing_receipt.get('customer_phone', '')
                },
                'company': {
                    'email': settings.get('company_email', 'company@example.com'),
                    'sno': settings.get('sno', 'usn_income'),
                    'inn': settings.get('inn', '1234567890'),
                    'payment_address': settings.get('payment_address', 'example.com')
                },
                'bulk_count': count,
                'original_uuid': uuid
            }
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'preview': True,
                    'receipt': parsed_receipt,
                    'original_user_message': existing_receipt.get('user_message', ''),
                    'operation_type': existing_receipt.get('operation_type', 'sell')
                })
            }
    
        repeat_uuid = detect_repeat_command(user_message)
        
        if not operation_type:
            operation_type = detect_operation_type(user_message)
        
        if repeat_uuid == 'LAST':
            existing_receipt = get_last_receipt_from_db()
            if existing_receipt:
                parsed_receipt = {
                    'items': existing_receipt['items'],
                    'total': existing_receipt['total'],
                    'payment_type': existing_receipt.get('payment_type', 'card'),
                    'payments': existing_receipt.get('payments', [{
                        'type': '0' if existing_receipt.get('payment_type') == 'cash' else '1',
                        'sum': existing_receipt['total']
                    }]),
                    'client': {
                        'email': existing_receipt.get('customer_email', ''),
                        'phone': existing_receipt.get('customer_phone', '')
                    },
                    'company': {
                        'email': settings.get('company_email', 'company@example.com'),
                        'sno': settings.get('sno', 'usn_income'),
                        'inn': settings.get('inn', '1234567890'),
                        'payment_address': settings.get('payment_address', 'example.com')
                    }
                }
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'success': True,
                        'message': f'Повторяю последний чек',
                        'receipt': parsed_receipt,
                        'operation_type': operation_type,
                        'preview': True,
                        'is_repeat': True
                    })
                }
            else:
                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': 'В истории нет чеков для повтора'
                    })
                }
        elif repeat_uuid:
            existing_receipt = get_receipt_from_db(repeat_uuid)
            if existing_receipt:
                print(f"[DEBUG] Repeat receipt UUID {repeat_uuid}: existing_receipt = {existing_receipt}")
                parsed_receipt = existing_receipt
                operation_type = existing_receipt.get('operation_type', 'sell')
                
                print(f"[DEBUG] Repeat receipt payments data: {parsed_receipt.get('payments')}")
                
                if 'company' not in parsed_receipt:
                    parsed_receipt['company'] = {}
                
                parsed_receipt['company']['email'] = settings.get('company_email', parsed_receipt.get('company', {}).get('email', ''))
                parsed_receipt['company']['inn'] = settings.get('inn', parsed_receipt.get('company', {}).get('inn', ''))
                parsed_receipt['company']['sno'] = settings.get('sno', parsed_receipt.get('company', {}).get('sno', 'usn_income'))
                parsed_receipt['company']['payment_address'] = settings.get('payment_address', parsed_receipt.get('company', {}).get('payment_address', ''))
                
                if not parsed_receipt.get('client', {}).get('email'):
                    company_email = settings.get('company_email', '')
                    if company_email:
                        if 'client' not in parsed_receipt:
                            parsed_receipt['client'] = {}
                        parsed_receipt['client']['email'] = company_email
                
                if preview_only:
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({
                            'success': True,
                            'message': f'Найден чек UUID {repeat_uuid}. Проверь данные перед повторной отправкой. При отправке будет создан новый external_id.',
                            'receipt': parsed_receipt,
                            'operation_type': operation_type,
                            'preview': True,
                            'is_repeat': True
                        })
                    }
            else:
                return {
                    'statusCode': 404,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': f'Чек с UUID {repeat_uuid} не найден в истории'
                    })
                }
        else:
            try:
                parsed_receipt = parse_receipt_from_text(user_message, settings)
            except ValueError as e:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': str(e),
                        'message': str(e)
                    })
                }
            
            if previous_receipt:
                parsed_receipt = merge_receipts(previous_receipt, parsed_receipt)
    
    if parsed_receipt.get('payments'):
        total_from_payments = sum(payment.get('sum', 0) for payment in parsed_receipt['payments'])
        if total_from_payments > 0:
            items_total = sum(item.get('price', 0) * item.get('quantity', 1) for item in parsed_receipt.get('items', []))
            if abs(items_total - total_from_payments) > 0.01:
                print(f"[DEBUG] Recalculating prices: items_total={items_total}, payments_total={total_from_payments}")
                if len(parsed_receipt.get('items', [])) == 1:
                    parsed_receipt['items'][0]['price'] = total_from_payments / parsed_receipt['items'][0].get('quantity', 1)
                    print(f"[DEBUG] Updated single item price to {parsed_receipt['items'][0]['price']}")
            parsed_receipt['total'] = total_from_payments
    
    # CRITICAL: Auto-apply payment provider if detected from keywords
    if auto_selected_provider and document_type == 'link':
        provider_id = auto_selected_provider.get('id')
        provider_name = auto_selected_provider.get('name', f'Провайдер {provider_id}')
        
        # Clean provider name
        provider_name = provider_name.replace('Платёж через счёт ', '')
        provider_name = provider_name.replace('Платёж через эквайринг ', '')
        provider_name = provider_name.replace('Платёж через ', '')
        provider_name = provider_name.replace('"', '')
        
        # Set payment provider in receipt_data
        parsed_receipt['payment_link_enabled'] = True
        parsed_receipt['payment_provider_id'] = int(provider_id)
        parsed_receipt['payment_provider_name'] = provider_name
        parsed_receipt['operation_type'] = 'sell'  # Always Продажа for payment link
        
        # Set provider ID as payment type
        if 'payments' in parsed_receipt and len(parsed_receipt['payments']) > 0:
            parsed_receipt['payments'][0]['type'] = int(provider_id)
            print(f"[DEBUG] Auto-applied payment provider: id={provider_id}, name={provider_name}")
    
    # CRITICAL: Validate payment link has proper item name (not "платежная ссылка")
    if document_type == 'link':
        items = parsed_receipt.get('items', [])
        if items and len(items) > 0:
            item_name = items[0].get('name', '').lower()
            # Check if item name is generic payment link keywords
            invalid_names = ['платежная ссылка', 'ссылка на оплату', 'ссылка', 'qr', 'эквайринг', 'платеж', 'оплата']
            if item_name in invalid_names or not item_name:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'success': False,
                        'message': '⚠️ Укажи товар или услугу для платежной ссылки.\n\n"Платежная ссылка" - это способ оплаты, а не товар.\n\nПример:\n• "Консультация 5000₽ ссылка Сбербанк"\n• "Подписка на месяц 1000₽ ссылка ЮКасса"'
                    })
                }
    
    # CRITICAL: If payment link requested but no provider selected, show error
    # Skip validation if edited_data already has payment_provider_id set
    has_provider_in_edited_data = parsed_receipt.get('payment_link_enabled') and parsed_receipt.get('payment_provider_id')
    if document_type == 'link' and not auto_selected_provider and not has_provider_in_edited_data:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'message': '⚠️ Для платежной ссылки нужно указать провайдера.\n\nУкажи провайдера в запросе:\n• Сбербанк\n• ЮКасса\n• Тинькофф\n• Альфа-Банк\n\nПример: "Консультация 5000₽ ссылка Сбербанк"\n\nИли подключи провайдеров в ЕкомКасса:\n🔗 https://app.ecomkassa.ru/admin/integrations'
            })
        }
    
    # CRITICAL: If provider keyword detected but provider not available, show error
    if detected_provider_keyword and document_type == 'link' and not auto_selected_provider:
        provider_name_ru = {
            'сбербанк': 'Сбербанк',
            'юкасса': 'ЮКасса',
            'тинькофф': 'Тинькофф',
            'альфа': 'Альфа-Банк',
            'втб': 'ВТБ',
            'райффайзен': 'Райффайзен',
            'газпромбанк': 'Газпромбанк',
            'россельхозбанк': 'Россельхозбанк',
            'открытие': 'Открытие',
            'промсвязьбанк': 'Промсвязьбанк'
        }.get(detected_provider_keyword, detected_provider_keyword.capitalize())
        
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'error': f'⚠️ Провайдер "{provider_name_ru}" не подключен.\n\nПодключи {provider_name_ru} в ЕкомКасса:\n🔗 https://app.ecomkassa.ru/admin/integrations\n\nПосле подключения создай чек заново.'
            })
        }
    
    if preview_only:
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'message': 'Предпросмотр чека',
                'receipt': parsed_receipt,
                'operation_type': operation_type,
                'document_type': document_type,  # CRITICAL: Pass document type to telegram-bot
                'preview': True
            })
        }
    
    print(f"[DEBUG] Before email check: parsed_receipt exists: {parsed_receipt is not None}")
    print(f"[DEBUG] parsed_receipt type: {type(parsed_receipt)}")
    print(f"[DEBUG] parsed_receipt.get('client'): {parsed_receipt.get('client') if isinstance(parsed_receipt, dict) else 'NOT A DICT'}")
    
    client_email = parsed_receipt.get('client', {}).get('email', '')
    
    print(f"[DEBUG] client_email: '{client_email}'")
    
    invalid_emails = ['customer@example.com', 'НЕ УКАЗАН email', 'email@example.com', '']
    if not client_email or client_email in invalid_emails or '@' not in client_email or '.' not in client_email:
        # Try to use company_email as fallback
        company_email = settings.get('company_email', '')
        print(f"[DEBUG] client_email invalid, trying company_email: '{company_email}'")
        
        if company_email and '@' in company_email and '.' in company_email:
            print(f"[DEBUG] Using company_email as fallback")
            parsed_receipt.setdefault('client', {})['email'] = company_email
        else:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Не указан email клиента',
                    'message': 'Укажи email клиента в сообщении или добавь company_email в настройках',
                    'missing_field': 'email'
                })
            }
    
    login = settings.get('ecomkassa_login') or os.environ.get('ECOMKASSA_LOGIN', '')
    password = settings.get('ecomkassa_password') or os.environ.get('ECOMKASSA_PASSWORD', '')
    group_code = settings.get('group_code') or os.environ.get('ECOMKASSA_GROUP_CODE', '')
    
    external_id = f'AI_{abs(hash(user_message + str(parsed_receipt)))}'
    
    if not (login and password and group_code):
        demo_result = {
            'success': True,
            'message': 'Чек обработан (демо-режим без учетных данных)',
            'receipt': parsed_receipt,
            'operation_type': operation_type,
            'demo': True
        }
        save_receipt_to_db(external_id, user_message, parsed_receipt, operation_type, None, True, None, user_id)
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(demo_result)
        }
    
    token = get_ecomkassa_token(login, password)
    
    if not token:
        error_result = {
            'success': False,
            'message': 'Не удалось авторизоваться в екомкасса',
            'receipt': parsed_receipt,
            'operation_type': operation_type,
            'demo': True
        }
        save_receipt_to_db(external_id, user_message, parsed_receipt, operation_type, None, True, None, user_id)
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(error_result)
        }
    
    bulk_count = parsed_receipt.get('bulk_count')
    original_uuid = parsed_receipt.get('original_uuid')
    
    if bulk_count and original_uuid:
        print(f"[DEBUG] Bulk creation confirmed: {bulk_count} copies of {original_uuid}")
        created_receipts = []
        failed_receipts = []
        
        for i in range(bulk_count):
            import time
            unique_external_id = f'BULK_{original_uuid}_{int(time.time() * 1000)}_{i}'
            print(f"[DEBUG] Creating copy {i+1}/{bulk_count} with external_id: {unique_external_id}")
            
            receipt_copy = parsed_receipt.copy()
            receipt_copy.pop('bulk_count', None)
            receipt_copy.pop('original_uuid', None)
            
            try:
                result = create_ecomkassa_receipt(receipt_copy, token, group_code, operation_type)
                print(f"[DEBUG] Copy {i+1} result: success={result.get('success')}")
                
                if result.get('success') or result.get('demo'):
                    save_receipt_to_db(
                        unique_external_id,
                        f'Копия #{i+1} чека {original_uuid}',
                        receipt_copy,
                        operation_type,
                        result.get('ecomkassa_response'),
                        result.get('demo', False),
                        result.get('uuid'),
                        user_id
                    )
                    created_receipts.append({
                        'index': i+1,
                        'uuid': result.get('uuid'),
                        'external_id': unique_external_id
                    })
                else:
                    failed_receipts.append({
                        'index': i+1,
                        'error': result.get('error', 'Неизвестная ошибка')
                    })
            except Exception as e:
                print(f"[DEBUG] Copy {i+1} exception: {str(e)}")
                failed_receipts.append({'index': i+1, 'error': str(e)})
        
        print(f"[DEBUG] Bulk creation finished: created={len(created_receipts)}, failed={len(failed_receipts)}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'isBase64Encoded': False,
            'body': json.dumps({
                'success': True,
                'message': f'Копии чека {original_uuid} были отправлены: {len(created_receipts)} штук',
                'created': created_receipts,
                'failed': failed_receipts,
                'total_requested': bulk_count,
                'total_created': len(created_receipts),
                'total_failed': len(failed_receipts)
            })
        }
    
    # CRITICAL: Check payment_provider_id for document_type='link'
    if document_type == 'link':
        payment_provider_id = parsed_receipt.get('payment_provider_id')
        payment_link_enabled = parsed_receipt.get('payment_link_enabled', False)
        
        # Check if payment provider is selected
        if not payment_link_enabled or not payment_provider_id:
            print(f"[ERROR] Payment link requested but provider not selected. payment_link_enabled={payment_link_enabled}, payment_provider_id={payment_provider_id}")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'isBase64Encoded': False,
                'body': json.dumps({
                    'success': False,
                    'error': '⚠️ Для платежной ссылки необходимо выбрать платежного провайдера.\n\nНажми "Изменить" → "Документ и оплата" → "Способ оплаты" и выбери провайдера (Сбербанк, ЮКасса и т.д.)'
                })
            }
        
        print(f"[DEBUG] Payment link validation passed: provider_id={payment_provider_id}")
    
    receipt_result = create_ecomkassa_receipt(
        parsed_receipt, 
        token, 
        group_code,
        operation_type
    )
    
    save_receipt_to_db(
        external_id,
        user_message,
        parsed_receipt,
        operation_type,
        receipt_result.get('ecomkassa_response'),
        receipt_result.get('demo', False),
        receipt_result.get('uuid'),
        user_id
    )
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'isBase64Encoded': False,
        'body': json.dumps(receipt_result)
    }


def get_ecomkassa_token(login: str, password: str) -> Optional[str]:
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


def merge_receipts(previous: dict, new: dict) -> dict:
    result = previous.copy()
    
    if new.get('client', {}).get('email') and new['client']['email'] != 'customer@example.com':
        if 'client' not in result:
            result['client'] = {}
        result['client']['email'] = new['client']['email']
    
    if new.get('items') and len(new['items']) > 0:
        first_item = new['items'][0]
        if first_item.get('name') != 'Товар/Услуга':
            result['items'] = new['items']
            result['total'] = new.get('total', result.get('total', 0))
    
    if new.get('company'):
        if 'company' not in result:
            result['company'] = {}
        for key, value in new['company'].items():
            if value and value not in ['example@company.ru', 'None', '']:
                result['company'][key] = value
    
    return result


def detect_bulk_with_ai(text: str, settings: dict) -> Optional[tuple]:
    '''
    AI-powered bulk command detection
    Returns (count, uuid) tuple or None
    '''
    import json
    
    text_lower = text.lower()
    bulk_keywords = ['копи', 'дубл', 'повтор', 'еще', 'ещё', 'раз', 'штук']
    has_bulk_keyword = any(kw in text_lower for kw in bulk_keywords)
    has_number = any(char.isdigit() for char in text)
    
    if not (has_bulk_keyword and has_number):
        return None
    
    print(f"[DEBUG] AI bulk detection for: {text}")
    
    active_provider = settings.get('active_ai_provider', '')
    
    prompt = f"""Ты ИИ-помощник. Анализируй запрос и определи, просит ли пользователь создать копии/дубли чека.

Запрос: "{text}"

Если это команда на создание копий чека:
1. Найди КОЛИЧЕСТВО копий (число)
2. Найди UUID/ID чека (последовательность цифр и букв, обычно 8+ символов)

Примеры:
- "105000516 сделай 2 дубля" → {{"bulk": true, "count": 2, "uuid": "105000516"}}
- "создай 5 копий чека 12345678" → {{"bulk": true, "count": 5, "uuid": "12345678"}}
- "повтори 3 раза abc123def" → {{"bulk": true, "count": 3, "uuid": "abc123def"}}
- "еще 10 штук номер 999888" → {{"bulk": true, "count": 10, "uuid": "999888"}}

Если это НЕ команда на копирование:
{{"bulk": false}}

ВАЖНО: Отвечай ТОЛЬКО валидным JSON, без дополнительного текста."""

    if active_provider == 'gptunnel_chatgpt':
        import requests
        api_key = settings.get('gptunnel_api_key', '')
        model = settings.get('gptunnel_selected_model', 'gpt-4')
        
        if not api_key:
            return None
        
        try:
            response = requests.post(
                'https://gptunnel.ru/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.1,
                    'max_tokens': 150
                },
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            result = response.json()
            ai_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"[DEBUG] AI bulk detection response: {ai_text}")
            
            parsed = extract_json_from_text(ai_text)
            if parsed and parsed.get('bulk'):
                count = int(parsed.get('count', 0))
                uuid = str(parsed.get('uuid', ''))
                if count > 0 and uuid:
                    print(f"[DEBUG] AI detected bulk: count={count}, uuid={uuid}")
                    return (count, uuid)
        except Exception as e:
            print(f"[ERROR] AI bulk detection failed: {e}")
            return None
    
    return None


def detect_bulk_repeat_command(text: str) -> Optional[tuple]:
    import re
    text_lower = text.lower()
    
    bulk_patterns = [
        r'(?:создай|сделай|отправ[иь])\s+(\d+)\s+(?:копи[йи]|дубл[ей]я?|чек[ао]в?)\s+(?:чека?)?\s*№?\s*([a-zA-Z0-9_-]+)',
        r'(\d+)\s+(?:копи[йи]|дубл[ей]я?|раз[аы]?)\s+(?:чека?)?\s*№?\s*([a-zA-Z0-9_-]+)',
        r'(?:создай|сделай)\s+(\d+)\s+штук\s+(?:чека?)?\s*№?\s*([a-zA-Z0-9_-]+)',
        r'(\d+)\s+(?:копи[йи]|дубл[ей]я?)\s+№?\s*([a-zA-Z0-9_-]+)',
        r'([a-zA-Z0-9_-]{8,})\s+(?:создай|сделай)\s+(\d+)\s+(?:копи[йи]|дубл[ей]я?|чек[ао]в?)',
        r'([a-zA-Z0-9_-]{8,})\s+(\d+)\s+(?:копи[йи]|дубл[ей]я?|раз[аы]?)'
    ]
    
    print(f"[DEBUG] Detecting bulk command in: {text_lower}")
    
    for i, pattern in enumerate(bulk_patterns):
        match = re.search(pattern, text_lower)
        if match:
            if i >= 4:
                uuid_raw = match.group(1)
                count = int(match.group(2))
            else:
                count = int(match.group(1))
                uuid_raw = match.group(2)
            print(f"[DEBUG] Pattern {i} matched! Count: {count}, UUID raw: {uuid_raw}")
            uuid_clean = extract_uuid_with_ai(uuid_raw)
            result_uuid = uuid_clean if uuid_clean else uuid_raw
            print(f"[DEBUG] Final UUID: {result_uuid}")
            return (count, result_uuid)
    
    print(f"[DEBUG] No bulk pattern matched")
    return None


def detect_repeat_command(text: str) -> Optional[str]:
    import re
    text_lower = text.lower()
    
    repeat_with_uuid_patterns = [
        r'повтор[иь]\s+чек\s+№?\s*([a-zA-Z0-9_-]+)',
        r'повтор[иь]\s+№?\s*([a-zA-Z0-9_-]+)',
        r'отправ[иь]\s+снова\s+№?\s*([a-zA-Z0-9_-]+)',
        r'пересоздай\s+чек\s+№?\s*([a-zA-Z0-9_-]+)',
        r'создай\s+заново\s+№?\s*([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in repeat_with_uuid_patterns:
        match = re.search(pattern, text_lower)
        if match:
            uuid_raw = match.group(1)
            uuid_clean = extract_uuid_with_ai(uuid_raw)
            return uuid_clean if uuid_clean else uuid_raw
    
    repeat_without_uuid_patterns = [
        r'повтор[иь]\s+чек',
        r'повтор[иь]\s+последний',
        r'отправ[иь]\s+снова',
        r'пересоздай\s+чек',
        r'создай\s+заново'
    ]
    
    for pattern in repeat_without_uuid_patterns:
        if re.search(pattern, text_lower):
            return 'LAST'
    
    return None


def extract_uuid_with_ai(text: str) -> Optional[str]:
    import re
    uuid_pattern = r'\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}|[a-zA-Z0-9]{8,})\b'
    match = re.search(uuid_pattern, text.lower())
    if match:
        return match.group(1)
    cleaned = re.sub(r'[^a-zA-Z0-9-]', '', text)
    if len(cleaned) >= 8:
        return cleaned
    return None


def get_receipt_from_db(uuid_search: str) -> Optional[Dict[str, Any]]:
    database_url = os.environ.get('DATABASE_URL', '')
    if not database_url:
        return None
    
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(
            "SELECT external_id, user_message, operation_type, items, total, "
            "payment_type, payments, customer_email, ecomkassa_response FROM t_p7891941_voice_ai_agent_1.receipts "
            "WHERE ecomkassa_response->>'uuid' = %s LIMIT 1",
            (uuid_search,)
        )
        
        receipt = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if receipt:
            payments_data = receipt.get('payments') or [{
                'type': '0' if receipt['payment_type'] == 'cash' else '1',
                'sum': float(receipt['total'])
            }]
            
            return {
                'original_external_id': receipt['external_id'],
                'user_message': receipt['user_message'],
                'operation_type': receipt['operation_type'],
                'items': receipt['items'],
                'total': float(receipt['total']),
                'payment_type': receipt['payment_type'],
                'client': {
                    'email': receipt['customer_email']
                },
                'payments': payments_data
            }
        
        return None
    except Exception as e:
        print(f"[DEBUG] Error getting receipt from DB: {str(e)}")
        return None


def get_last_receipt_from_db() -> Optional[Dict[str, Any]]:
    database_url = os.environ.get('DATABASE_URL', '')
    if not database_url:
        return None
    
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(
            "SELECT external_id, user_message, operation_type, items, total, "
            "payment_type, payments, customer_email, ecomkassa_response "
            "FROM t_p7891941_voice_ai_agent_1.receipts "
            "WHERE status = 'success' AND demo_mode = false "
            "ORDER BY created_at DESC LIMIT 1"
        )
        
        receipt = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if receipt:
            payments_data = receipt.get('payments') or [{
                'type': '0' if receipt['payment_type'] == 'cash' else '1',
                'sum': float(receipt['total'])
            }]
            
            return {
                'original_external_id': receipt['external_id'],
                'user_message': receipt['user_message'],
                'operation_type': receipt['operation_type'],
                'items': receipt['items'],
                'total': float(receipt['total']),
                'payment_type': receipt['payment_type'],
                'customer_email': receipt['customer_email'],
                'payments': payments_data
            }
        
        return None
    except Exception as e:
        print(f"[DEBUG] Error getting last receipt from DB: {str(e)}")
        return None


def detect_operation_type(text: str) -> str:
    text_lower = text.lower()
    
    refund_keywords = [
        'возврат', 'верни', 'вернуть', 'refund', 'отмен',
        'верну', 'возвращ', 'отказ'
    ]
    
    correction_keywords = [
        'коррекция', 'исправ', 'корректир', 'ошибк'
    ]
    
    refund_correction_keywords = [
        'коррекция расход', 'исправить расход', 'под отчет'
    ]
    
    sell_correction_keywords = [
        'коррекция прихода', 'исправить приход', 'коррекция продаж'
    ]
    
    for keyword in refund_correction_keywords:
        if keyword in text_lower:
            return 'refund_correction'
    
    for keyword in sell_correction_keywords:
        if keyword in text_lower:
            return 'sell_correction'
    
    for keyword in refund_keywords:
        if keyword in text_lower:
            return 'refund'
    
    for keyword in correction_keywords:
        if keyword in text_lower:
            return 'sell_correction'
    
    return 'sell'


def get_gigachat_token(auth_key: str) -> Optional[str]:
    import requests
    
    token_url = 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
    
    headers = {
        'Authorization': f'Basic {auth_key}',
        'RqUID': str(uuid.uuid4()),
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'scope': 'GIGACHAT_API_PERS'
    }
    
    try:
        response = requests.post(token_url, headers=headers, data=data, verify=False, timeout=10)
        response_data = response.json()
        return response_data.get('access_token')
    except Exception as e:
        return None


def parse_receipt_from_text(text: str, settings: dict = None) -> Dict[str, Any]:
    import re
    
    if settings is None:
        settings = {}
    
    text_lower = text.lower().strip()
    greeting_patterns = [
        r'^привет',
        r'^здравствуй',
        r'^добр[ыо]',
        r'^hello',
        r'^hi\b',
        r'^hey\b',
        r'^расскажи',
        r'^что такое',
        r'^как дела',
        r'^анекдот',
        r'^пошути',
        r'^кто ты',
        r'^помоги',
        r'^спасибо'
    ]
    
    for pattern in greeting_patterns:
        if re.match(pattern, text_lower):
            raise ValueError(
                'Я ИИ-кассир и помогаю только с созданием чеков. '
                'Укажи товар/услугу, цену и email клиента для создания чека.'
            )
    
    active_provider = settings.get('active_ai_provider', '')
    has_any_ai = any([
        settings.get('gigachat_auth_key'),
        settings.get('openrouter_api_key'),
        settings.get('anthropic_api_key'),
        settings.get('openai_api_key'),
        settings.get('yandexgpt_api_key'),
        settings.get('gptunnel_api_key')
    ])
    
    if not has_any_ai and not active_provider:
        print("[INFO] No AI provider configured, using fallback")
        return fallback_parse_receipt(text, settings)
    
    print(f"[DEBUG] === AI Request ===")
    print(f"[DEBUG] User message: {text[:100]}")
    print(f"[DEBUG] Active provider: {active_provider}")
    
    context = settings.get('context_message', '')
    print(f"[DEBUG] Context from previous request: '{context}'")
    parsed_data = get_ai_completion(text, settings, context)
    
    if not parsed_data:
        print("[WARN] AI parsing failed, using fallback")
        return fallback_parse_receipt(text, settings)
    
    print(f"[DEBUG] Parsed data: {parsed_data}")
    
    if 'error' in parsed_data:
        raise ValueError(parsed_data.get('error', 'Не хватает данных для создания чека'))
    
    client_data = parsed_data.get('client', {})
    client_email = client_data.get('email', '') or ''
    
    if not client_email or client_email.strip() == '':
        client_email = settings.get('company_email', 'company@example.com')
        print(f"[DEBUG] Client email empty, using default: {client_email}")
    
    items = parsed_data.get('items', [])
    default_vat = settings.get('default_vat', 'none')
    for item in items:
        if 'vat' not in item or item['vat'] == 'none':
            item['vat'] = default_vat
    
    total = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
    
    if 'payments' in parsed_data and isinstance(parsed_data['payments'], list) and len(parsed_data['payments']) > 0:
        payments = parsed_data['payments']
    else:
        payment_type_raw = parsed_data.get('payment_type', 'electronically')
        payment_type_map = {
            'cash': '0',
            'electronically': '1',
            'prepaid': '2',
            'credit': '3',
            'other': '4'
        }
        payment_type = payment_type_map.get(payment_type_raw, '1')
        payments = [{
            'type': payment_type,
            'sum': round(total, 2)
        }]
    
    return {
        'items': items,
        'total': round(total, 2),
        'payments': payments,
        'client': {'email': client_email, 'phone': client_data.get('phone')},
        'company': {
            'email': settings.get('company_email', 'company@example.com'),
            'sno': settings.get('sno', 'usn_income'),
            'inn': settings.get('inn', '1234567890'),
            'payment_address': settings.get('payment_address', 'example.com')
        }
    }


def fallback_parse_receipt(text: str, settings: dict = None) -> Dict[str, Any]:
    import re
    
    if settings is None:
        settings = {}
    
    text_lower = text.lower().strip()
    greeting_patterns = [
        r'^привет',
        r'^здравствуй',
        r'^добр[ыо]',
        r'^hello',
        r'^hi\b',
        r'^hey\b',
        r'^расскажи',
        r'^что такое',
        r'^как дела',
        r'^анекдот',
        r'^пошути'
    ]
    
    for pattern in greeting_patterns:
        if re.match(pattern, text_lower):
            raise ValueError(
                'Я ИИ-кассир и помогаю только с созданием чеков. '
                'Укажи товар/услугу, цену и email клиента для создания чека.'
            )
    
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    customer_email = email_match.group(0) if email_match else settings.get('company_email', '')
    
    phone_match = re.search(r'\+?[78][\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}', text)
    customer_phone = phone_match.group(0) if phone_match else None
    
    text_clean = text.lower()
    skip_words = ['чек', 'создай', 'создать', 'сделай', 'сделать', 'оформи', 'оформить', 'пробей', 'отправь', 'для', 'на']
    for word in skip_words:
        text_clean = re.sub(r'\b' + word + r'\b', '', text_clean)
    
    text_clean = re.sub(r'\b(продажу|продаже|возврат|коррекция|коррекцию)\b', '', text_clean)
    
    item_patterns = re.findall(r'([а-яА-ЯёЁa-zA-Z]+(?:\s+[а-яА-ЯёЁa-zA-Z]+)*?)\s+(\d+(?:[\.,]\d{1,2})?)\s*(?:руб|₽|рублей)?', text_clean, re.IGNORECASE)
    
    items = []
    total = 0
    
    default_vat = settings.get('default_vat', 'none')
    
    service_keywords = [
        'консультация', 'стрижка', 'доставка', 'ремонт', 'услуга',
        'обучение', 'тренинг', 'коучинг', 'массаж', 'сервис',
        'поддержка', 'настройка', 'установка', 'монтаж'
    ]
    
    if item_patterns:
        for item_name_raw, price_str in item_patterns:
            item_name = item_name_raw.strip()
            price_val = round(float(price_str.replace(',', '.')), 2)
            
            item_lower = item_name.lower()
            payment_object = 'service' if any(kw in item_lower for kw in service_keywords) else 'commodity'
            
            items.append({
                'name': item_name.capitalize(), 
                'price': price_val, 
                'quantity': 1,
                'measure': 0,
                'vat': default_vat,
                'payment_method': 'full_payment',
                'payment_object': payment_object
            })
            total += price_val
    else:
        # Fallback: ищем просто цену
        price_matches = re.findall(r'(\d+(?:[\.,]\d{1,2})?)\s*(?:руб|₽|рублей)', text.lower())
        
        if price_matches:
            for price_str in price_matches:
                price_val = round(float(price_str.replace(',', '.')), 2)
                items.append({
                    'name': 'Товар', 
                    'price': price_val, 
                    'quantity': 1,
                    'measure': 0,
                    'vat': default_vat,
                    'payment_method': 'full_payment',
                    'payment_object': 'commodity'
                })
                total += price_val
    
    if not items:
        items.append({
            'name': 'Товар', 
            'price': 100.00, 
            'quantity': 1,
            'measure': 0,
            'vat': default_vat,
            'payment_method': 'full_payment',
            'payment_object': 'commodity'
        })
        total = 100.00
    
    payment_type_raw = 'electronically'
    if 'налич' in text.lower() or 'наличные' in text.lower():
        payment_type_raw = 'cash'
    
    payment_type_map = {
        'cash': '0',
        'electronically': '1'
    }
    payment_type = payment_type_map.get(payment_type_raw, '1')
    
    return {
        'items': items,
        'total': round(total, 2),
        'payments': [{
            'type': payment_type,
            'sum': round(total, 2)
        }],
        'client': {
            'email': customer_email,
            'phone': customer_phone
        },
        'company': {
            'email': settings.get('company_email', 'company@example.com'),
            'sno': settings.get('sno', 'usn_income'),
            'inn': settings.get('inn', '1234567890'),
            'payment_address': settings.get('payment_address', 'example.com')
        }
    }


def create_ecomkassa_receipt(
    receipt_data: Dict[str, Any], 
    token: str,
    group_code: str,
    operation_type: str = 'sell'
) -> Dict[str, Any]:
    
    operation_mapping = {
        'sell': 'sell',
        'refund': 'sell_refund',
        'sell_correction': 'sell_correction',
        'refund_correction': 'buy_refund_correction'
    }
    
    api_operation_type = operation_mapping.get(operation_type, 'sell')
    
    api_url = f'https://app.ecomkassa.ru/fiscalorder/v5/{group_code}/{api_operation_type}'
    
    from datetime import datetime
    import time
    
    client_data = receipt_data.get('client', {})
    company_data = receipt_data.get('company', {})
    
    measure_map = {
        'шт': '0',
        'г': '10',
        'кг': '11',
        'т': '12',
        'см': '20',
        'дм': '21',
        'м': '22',
        'кв.см': '30',
        'кв.дм': '31',
        'кв.м': '32',
        'мл': '40',
        'л': '41',
        'куб.м': '42',
        'кВт⋅ч': '50',
        'Гкал': '51',
        'сутки': '70',
        'час': '71',
        'мин': '72',
        'сек': '73',
        'кБ': '80',
        'МБ': '81',
        'ГБ': '82',
        'ТБ': '83',
        'услуга': '255'
    }
    
    # Build items, split fractional quantities to ensure price * quantity = sum
    from decimal import Decimal, ROUND_HALF_UP
    import math
    
    items_for_payload = []
    for item in receipt_data['items']:
        qty_decimal = Decimal(str(item.get('quantity', 1)))
        price_decimal = Decimal(str(item['price']))
        total_sum = float((price_decimal * qty_decimal).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        
        # If quantity has fractional part, split into integer + fraction
        qty_float = float(qty_decimal)
        qty_int = math.floor(qty_float)
        qty_frac = qty_float - qty_int
        
        if qty_frac > 0.001:  # Has fractional part
            # Integer part
            if qty_int > 0:
                price_rounded = float(price_decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
                int_sum = float((Decimal(str(price_rounded)) * Decimal(str(qty_int))).quantize(Decimal('0.01')))
                
                items_for_payload.append({
                    'name': item['name'],
                    'price': price_rounded,
                    'quantity': qty_int,
                    'sum': int_sum,
                    'measure': int(measure_map.get(item.get('measure', 'шт'), '0')),
                    'payment_method': item.get('payment_method', 'full_payment'),
                    'payment_object': {
                        'commodity': 1,
                        'excise': 2,
                        'job': 3,
                        'service': 4
                    }.get(item.get('payment_object'), 4),
                    'vat': {'type': item.get('vat', 'none')}
                })
            else:
                int_sum = 0
            
            # Fractional part with adjusted price to match total
            frac_sum = round(total_sum - int_sum, 2)
            frac_price = float((Decimal(str(frac_sum)) / Decimal(str(qty_frac))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            
            items_for_payload.append({
                'name': item['name'],
                'price': frac_price,
                'quantity': qty_frac,
                'sum': frac_sum,
                'measure': int(measure_map.get(item.get('measure', 'шт'), '0')),
                'payment_method': item.get('payment_method', 'full_payment'),
                'payment_object': {
                    'commodity': 1,
                    'excise': 2,
                    'job': 3,
                    'service': 4
                }.get(item.get('payment_object'), 4),
                'vat': {'type': item.get('vat', 'none')}
            })
        else:
            # No fractional part - simple calculation
            price_rounded = float(price_decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            item_sum = float((Decimal(str(price_rounded)) * qty_decimal).quantize(Decimal('0.01')))
            
            items_for_payload.append({
                'name': item['name'],
                'price': price_rounded,
                'quantity': float(qty_decimal),
                'sum': item_sum,
                'measure': int(measure_map.get(item.get('measure', 'шт'), '0')),
                'payment_method': item.get('payment_method', 'full_payment'),
                'payment_object': {
                    'commodity': 1,
                    'excise': 2,
                    'job': 3,
                    'service': 4
                }.get(item.get('payment_object'), 4),
                'vat': {'type': item.get('vat', 'none')}
            })
    
    calculated_total = round(sum(item['sum'] for item in items_for_payload), 2)
    
    # Get payment total from actual payments
    payments_list = receipt_data.get('payments', [{'type': 1, 'sum': calculated_total}])
    payment_total = round(sum(float(p.get('sum', 0)) for p in payments_list), 2)
    
    # Fix rounding: adjust last item price to match payment total
    # Ecomkassa validates: price * quantity == sum for each item
    # Use Decimal for precise money calculations
    from decimal import Decimal, ROUND_HALF_UP
    
    items_total = round(sum(item['sum'] for item in items_for_payload), 2)
    if items_total != payment_total and len(items_for_payload) > 0:
        difference = round(payment_total - items_total, 2)
        last_item = items_for_payload[-1]
        # Recalculate last item: new_sum = old_sum + difference, new_price = new_sum / quantity
        new_sum = round(last_item['sum'] + difference, 2)
        last_item['sum'] = new_sum
        
        # Use Decimal for exact calculation
        sum_decimal = Decimal(str(new_sum))
        qty_decimal = Decimal(str(last_item['quantity']))
        price_decimal = sum_decimal / qty_decimal
        
        # Round to 2 decimals
        price_rounded = float(price_decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        last_item['price'] = price_rounded
        
        # Verify: recalculate sum with rounded price
        verify_sum = round(price_rounded * last_item['quantity'], 2)
        print(f"[DEBUG] Adjusted last item: price={price_rounded}, sum={new_sum}, verify_sum={verify_sum}, payment_total={payment_total}")
    
    unique_id = f'AI_{int(time.time() * 1000000)}'
    
    ecomkassa_payload = {
        'external_id': unique_id,
        'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
        'receipt': {
            'client': {
                'email': client_data.get('email', '')
            },
            'company': {
                'email': company_data.get('email', ''),
                'sno': company_data.get('sno', 'usn_income'),
                'inn': company_data.get('inn', ''),
                'payment_address': company_data.get('payment_address', '')
            },
            'items': items_for_payload,
            'payments': [
                {
                    'type': int(payment.get('type', 1)),  # CRITICAL: Support provider IDs (103, 102, etc.) for payment links
                    'sum': float(payment.get('sum', payment_total))
                }
                for payment in payments_list
            ],
            'total': payment_total
        }
    }
    
    print(f"[DEBUG] Sending to ecomkassa: {api_url}")
    print(f"[DEBUG] Payload: {json.dumps(ecomkassa_payload, ensure_ascii=False, indent=2)}")
    
    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(ecomkassa_payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Token': token
            },
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=15) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            print(f"[DEBUG] Ecomkassa success response: {json.dumps(response_data, ensure_ascii=False)}")
            
            uuid = response_data.get('uuid', '')
            permalink = response_data.get('permalink', '')
            
            payment_link = response_data.get('invoice_payload', {}).get('link', '')
            qr_code = response_data.get('qr_code', '')
            
            return {
                'success': True,
                'message': 'Чек успешно создан в екомкасса',
                'uuid': uuid,
                'permalink': permalink,
                'payment_link': payment_link,
                'qr_code': qr_code,
                'receipt': receipt_data,
                'ecomkassa_response': response_data,
                'operation_type': operation_type
            }
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"[DEBUG] Ecomkassa HTTP error {e.code}: {error_body}")
        return {
            'success': False,
            'message': f'Ошибка API екомкасса: {e.code}',
            'receipt': receipt_data,
            'error': error_body,
            'demo': True
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': f'Ошибка при создании чека: {str(e)}',
            'receipt': receipt_data,
            'demo': True
        }


def save_receipt_to_db(
    external_id: str,
    user_message: str,
    receipt_data: Dict[str, Any],
    operation_type: str,
    ecomkassa_response: Optional[Dict[str, Any]],
    demo_mode: bool,
    uuid: Optional[str] = None,
    user_id: str = ''
) -> None:
    database_url = os.environ.get('DATABASE_URL', '')
    
    if not database_url:
        return
    
    import psycopg2
    
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Определяем payment_type для отображения (первый тип оплаты)
        payments = receipt_data.get('payments', [])
        payment_type_display = payments[0].get('type', '1') if payments else receipt_data.get('payment_type', 'card')
        
        cursor.execute(
            'INSERT INTO receipts (external_id, user_id, user_message, operation_type, items, total, '
            'payment_type, payments, customer_email, ecomkassa_response, status, demo_mode, uuid) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) '
            'ON CONFLICT (external_id) DO UPDATE SET '
            'ecomkassa_response = EXCLUDED.ecomkassa_response, '
            'payments = EXCLUDED.payments, '
            'status = EXCLUDED.status, '
            'uuid = EXCLUDED.uuid, '
            'updated_at = CURRENT_TIMESTAMP',
            (
                external_id,
                user_id,
                user_message,
                operation_type,
                json.dumps(receipt_data['items']),
                receipt_data['total'],
                payment_type_display,
                json.dumps(payments) if payments else None,
                receipt_data.get('customer_email'),
                json.dumps(ecomkassa_response) if ecomkassa_response else None,
                'success' if not demo_mode else 'demo',
                demo_mode,
                uuid
            )
        )
        
        conn.commit()
        cursor.close()
        conn.close()
    
    except Exception:
        pass