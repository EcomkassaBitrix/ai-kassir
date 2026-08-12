export interface ApiField {
  name: string;
  type: string;
  required: boolean;
  description: string;
}

export interface ApiError {
  code: number;
  description: string;
}

export interface ApiMethod {
  id: string;
  name: string;
  httpMethods: string[];
  auth?: string;
  description: string;
  headers?: ApiField[];
  queryParams?: ApiField[];
  requestFields?: ApiField[];
  requestExample?: string;
  responseExample: string;
  errors: ApiError[];
  notes?: string;
}

export const apiMethods: ApiMethod[] = [
  {
    id: 'process-receipt',
    name: 'process-receipt',
    httpMethods: ['POST', 'OPTIONS'],
    description:
      'Основной метод. Превращает текст на естественном языке ("Кофе 200₽ безнал") в структуру чека и, если это не предпросмотр — отправляет его в кассу Ecomkassa.',
    headers: [
      { name: 'X-User-Id', type: 'string', required: false, description: 'ID пользователя — если передан, подтягиваются его сохранённые настройки кассы' }
    ],
    requestFields: [
      { name: 'message', type: 'string', required: true, description: 'Текст запроса на естественном языке' },
      { name: 'operation_type', type: 'string', required: false, description: 'sell | refund | sell_correction | refund_correction' },
      { name: 'preview_only', type: 'boolean', required: false, description: 'true — только распознать и вернуть предпросмотр, ничего не отправляя' },
      { name: 'document_type', type: 'string', required: false, description: 'receipt (обычный чек) | link (платёжная ссылка)' },
      { name: 'settings', type: 'object', required: false, description: 'Данные кассы; при наличии X-User-Id дополняются сохранёнными в БД' },
      { name: 'edited_data', type: 'object', required: false, description: 'Данные чека после ручного редактирования пользователем' },
      { name: 'previous_receipt', type: 'object', required: false, description: 'Чек из предыдущего шага диалога' }
    ],
    requestExample: `{
  "message": "Кофе 200₽ test@mail.ru",
  "operation_type": "sell",
  "preview_only": true,
  "document_type": "receipt",
  "settings": {
    "ecomkassa_login": "...",
    "ecomkassa_password": "...",
    "group_code": "...",
    "company_email": "...",
    "inn": "...",
    "sno": "usn_income",
    "payment_address": "...",
    "default_vat": "none"
  }
}`,
    responseExample: `// preview_only=true
{
  "success": true,
  "preview": true,
  "operation_type": "sell",
  "document_type": "receipt",
  "receipt": {
    "items": [
      { "name": "Кофе", "price": 200, "quantity": 1, "measure": "шт",
        "vat": "none", "payment_method": "full_payment", "payment_object": "commodity" }
    ],
    "total": 200,
    "payments": [ { "type": "1", "sum": 200 } ],
    "client": { "email": "test@mail.ru", "phone": null },
    "company": { "email": "...", "sno": "usn_income", "inn": "...", "payment_address": "..." }
  }
}

// preview_only=false, чек отправлен
{
  "success": true,
  "uuid": "a1b2c3d4-...",
  "external_id": "AI_1710234567890",
  "permalink": "https://receipts.ecomkassa.ru/...",
  "payment_link": "https://app.ecomkassa.ru/pay/... (только для document_type=link)",
  "qr_code": "data:image/png;base64,... (только если есть payment_link)"
}`,
    errors: [
      { code: 200, description: 'успех (в т.ч. preview)' },
      { code: 400, description: 'пустое message, слишком короткий запрос без контекста, товар не указан для платёжной ссылки' },
      { code: 405, description: 'метод не POST' }
    ],
    notes: 'Типы платежей (payments[].type): 0=наличные, 1=безнал, 2=предоплата, 3=кредит, 4=иная форма, 5/6=расширенный аванс/кредит.'
  },
  {
    id: 'ecomkassa-proxy',
    name: 'ecomkassa-proxy',
    httpMethods: ['POST', 'OPTIONS'],
    description:
      'Низкоуровневый прокси к API кассы Ecomkassa (протокол ATOL Online v5). Сам получает токен по логину/паролю и выполняет запрос к нужному endpoint кассы. Используется внутри process-receipt, но доступен и напрямую.',
    requestFields: [
      { name: 'login', type: 'string', required: true, description: 'Логин кассы Ecomkassa' },
      { name: 'password', type: 'string', required: true, description: 'Пароль кассы Ecomkassa' },
      { name: 'endpoint', type: 'string', required: false, description: 'По умолчанию /fiscalorder/v5/default_group/sell' },
      { name: 'method', type: 'string', required: false, description: 'GET или POST, по умолчанию GET' },
      { name: 'payload', type: 'object', required: false, description: 'Тело запроса к кассе (обязательно для POST)' }
    ],
    requestExample: `{
  "login": "ecomkassa_login",
  "password": "ecomkassa_password",
  "endpoint": "/fiscalorder/v5/{group_code}/sell",
  "method": "POST",
  "payload": { "...": "items, payments, client, company" }
}`,
    responseExample: `// прямой ответ Ecomkassa + qr_code, если есть платёжная ссылка
{
  "code": 0,
  "uuid": "...",
  "invoice_payload": { "link": "https://..." },
  "qr_code": "data:image/png;base64,..."
}`,
    errors: [
      { code: 400, description: 'нет login/password, некорректный JSON, неподдерживаемый method' },
      { code: 401, description: 'неверные учётные данные Ecomkassa' },
      { code: 405, description: 'метод не POST' },
      { code: 500, description: 'сбой сети/запроса к Ecomkassa' }
    ]
  },
  {
    id: 'get-receipts',
    name: 'get-receipts',
    httpMethods: ['GET', 'OPTIONS'],
    description: 'История созданных чеков с пагинацией.',
    queryParams: [
      { name: 'limit', type: 'number', required: false, description: 'Сколько чеков вернуть (по умолчанию 50)' },
      { name: 'offset', type: 'number', required: false, description: 'Смещение для пагинации (по умолчанию 0)' }
    ],
    responseExample: `{
  "success": true,
  "receipts": [
    {
      "id": 1,
      "external_id": "AI_...",
      "user_id": "ecom_...",
      "user_message": "Кофе 200₽",
      "operation_type": "sell",
      "items": [ "..." ],
      "total": 200.0,
      "payment_type": "1",
      "customer_email": "test@mail.ru",
      "status": "success",
      "demo_mode": false,
      "created_at": "2025-12-03T12:31:15.95",
      "uuid": "a1b2c3d4"
    }
  ],
  "total": 135,
  "limit": 50,
  "offset": 0
}`,
    errors: [
      { code: 405, description: 'метод не GET' },
      { code: 500, description: 'БД не настроена / ошибка запроса' }
    ]
  },
  {
    id: 'user-settings',
    name: 'user-settings',
    httpMethods: ['GET', 'POST', 'OPTIONS'],
    description: 'Сохранение и загрузка индивидуальных настроек пользователя (данные кассы, ИНН, СНО, ключи ИИ).',
    headers: [
      { name: 'X-User-Id', type: 'string', required: true, description: 'Обязателен для GET и POST' }
    ],
    requestExample: `{
  "settings": {
    "group_code": "...", "inn": "...", "sno": "usn_income",
    "default_vat": "none", "company_email": "...", "payment_address": "...",
    "ecomkassa_login": "...", "ecomkassa_password": "...",
    "active_ai_provider": "...", "gigachat_auth_key": "...",
    "yandexgpt_api_key": "...", "yandexgpt_folder_id": "...", "gptunnel_api_key": "..."
  }
}`,
    responseExample: `// GET
{ "settings": { "group_code": "", "inn": "", "sno": "usn_income", "default_vat": "none" } }

// POST
{ "status": "saved", "settings": { "...": "то, что сохранено" } }`,
    errors: [
      { code: 400, description: 'нет заголовка X-User-Id' },
      { code: 405, description: 'метод не GET/POST' },
      { code: 500, description: 'БД не настроена' }
    ]
  },
  {
    id: 'ai-settings',
    name: 'ai-settings',
    httpMethods: ['GET', 'POST', 'OPTIONS'],
    auth: 'X-Admin-Token',
    description: 'Управление ИИ-провайдером для распознавания текста/голоса на уровне всего проекта (админ-функция). Проверяет валидность ключей перед сохранением.',
    headers: [
      { name: 'X-Admin-Token', type: 'string', required: true, description: 'Токен администратора' }
    ],
    requestFields: [
      { name: 'provider_id', type: 'string', required: false, description: 'gptunnel_chatgpt (текст) | yandex_speechkit (голос) | пусто (отключить)' },
      { name: 'selected_model', type: 'string', required: false, description: 'ID модели для GPTunnel' },
      { name: 'disable_type', type: 'string', required: false, description: 'text или voice — что отключать, если provider_id пуст' }
    ],
    requestExample: `{
  "provider_id": "gptunnel_chatgpt",
  "selected_model": "gpt-4o",
  "gptunnel_api_key": "...",
  "yandex_speechkit_key": "...",
  "disable_type": "text"
}`,
    responseExample: `// GET
{
  "text_provider": "gptunnel_chatgpt",
  "voice_provider": "yandex_speechkit",
  "selected_model": "gpt-4o",
  "available_providers": [
    { "id": "gptunnel_chatgpt", "name": "GPTunnel (мультимодели)", "has_secret": true },
    { "id": "yandex_speechkit", "name": "Yandex SpeechKit", "has_secret": false }
  ],
  "available_models": [ { "id": "gpt-4o", "name": "GPT-4o", "type": "TEXT" } ]
}

// POST
{
  "success": true,
  "active_provider": "gptunnel_chatgpt",
  "selected_model": "gpt-4o",
  "validation": { "valid": true, "message": "GPTunnel key and model are valid" }
}`,
    errors: [
      { code: 400, description: 'невалидный provider_id / отсутствует ключ / ключ не прошёл проверку' },
      { code: 401, description: 'нет X-Admin-Token' },
      { code: 405, description: 'метод не поддерживается' },
      { code: 500, description: 'БД не настроена' }
    ]
  },
  {
    id: 'admin-auth',
    name: 'admin-auth',
    httpMethods: ['POST', 'OPTIONS'],
    description: 'Вход в админ-панель по паролю, выдаёт токен для доступа к admin-stats, ai-settings, telegram-token.',
    requestExample: `{ "password": "..." }`,
    responseExample: `{ "token": "sha256-хеш", "expires_in": 86400 }`,
    errors: [
      { code: 401, description: 'неверный пароль' },
      { code: 405, description: 'метод не POST' },
      { code: 500, description: 'пароль админа не задан на сервере (секрет ADMIN_PASSWORD)' }
    ]
  },
  {
    id: 'admin-stats',
    name: 'admin-stats',
    httpMethods: ['GET', 'OPTIONS'],
    auth: 'X-Admin-Token',
    description: 'Статистика по отзывам пользователей (лайк/дизлайк на ответы ИИ) для админ-панели.',
    headers: [
      { name: 'X-Admin-Token', type: 'string', required: true, description: 'Токен администратора' }
    ],
    responseExample: `{
  "total": 40,
  "positive": 35,
  "negative": 5,
  "positive_rate": 87.5,
  "recent_feedback": [
    { "message_id": "...", "user_message": "первые 100 симв.",
      "agent_response": "первые 100 симв.", "feedback_type": "positive",
      "created_at": "2025-12-03T12:31:15" }
  ]
}`,
    errors: [
      { code: 401, description: 'нет токена' },
      { code: 405, description: 'метод не GET' },
      { code: 500, description: 'БД не настроена' }
    ],
    notes: 'Отдаёт последние 50 записей.'
  },
  {
    id: 'save-feedback',
    name: 'save-feedback',
    httpMethods: ['POST', 'OPTIONS'],
    description: 'Сохранение реакции пользователя (👍/👎) на ответ ИИ.',
    requestFields: [
      { name: 'message_id', type: 'string', required: true, description: 'ID сообщения' },
      { name: 'feedback_type', type: 'string', required: true, description: 'positive или negative' },
      { name: 'user_message', type: 'string', required: false, description: 'Текст запроса пользователя' },
      { name: 'agent_response', type: 'string', required: false, description: 'Текст ответа ИИ' }
    ],
    requestExample: `{
  "message_id": "msg_123",
  "user_message": "Создай чек на 100р",
  "agent_response": "Чек создан успешно",
  "feedback_type": "positive"
}`,
    responseExample: `{ "success": true, "message": "Feedback saved successfully" }`,
    errors: [
      { code: 400, description: 'нет message_id/feedback_type или неверное значение feedback_type' },
      { code: 405, description: 'метод не POST' },
      { code: 500, description: 'БД не настроена / ошибка записи' }
    ]
  },
  {
    id: 'telegram-bot',
    name: 'telegram-bot',
    httpMethods: ['POST', 'OPTIONS'],
    description:
      'Вебхук для Telegram-бота. Принимает обновления от Telegram (сообщения, голосовые, кнопки), создаёт чеки тем же способом, что и веб-версия, поддерживает команды /start, /help, /history, /repeat, повтор по UUID, редактирование через диалог.',
    requestExample: `// стандартный формат Telegram Update
{ "message": { "chat": { "id": 123 }, "text": "Кофе 200р" } }`,
    responseExample: `{ "ok": true }`,
    errors: [
      { code: 405, description: 'метод не POST' },
      { code: 500, description: 'токен бота не настроен (секрет)' }
    ],
    notes:
      'Команды: /start (или /start LINK-XXXX для привязки), /help, /history (последние 10 чеков с кнопками), /repeat, "повтори <id>", голосовые сообщения (распознаются через Yandex SpeechKit).'
  },
  {
    id: 'telegram-link',
    name: 'telegram-link',
    httpMethods: ['POST', 'OPTIONS'],
    description: 'Генерирует одноразовый код для привязки Telegram-аккаунта к текущему пользователю сайта.',
    headers: [
      { name: 'X-User-Id', type: 'string', required: true, description: 'Обязателен' }
    ],
    responseExample: `{
  "link_code": "LINK-Ab12Cd34",
  "bot_url": "https://t.me/ecomkassa_ai_bot?start=LINK-Ab12Cd34",
  "expires_at": "2025-12-04T14:15:00"
}`,
    errors: [
      { code: 400, description: 'нет X-User-Id' },
      { code: 405, description: 'метод не POST' },
      { code: 500, description: 'БД не настроена' }
    ],
    notes: 'Код действителен 24 часа.'
  },
  {
    id: 'telegram-token',
    name: 'telegram-token',
    httpMethods: ['GET', 'POST', 'OPTIONS'],
    auth: 'X-Admin-Token',
    description: 'Сохранение/чтение токена Telegram-бота и флага включения уведомлений (админ-функция).',
    headers: [
      { name: 'X-Admin-Token', type: 'string', required: true, description: 'Токен администратора' }
    ],
    requestExample: `{ "token": "123456:ABC-...", "enabled": true }`,
    responseExample: `// GET
{ "token": "123456:ABC-...", "enabled": true }

// POST
{ "success": true }`,
    errors: [
      { code: 400, description: 'пустой token при попытке его установить' },
      { code: 401, description: 'нет X-Admin-Token' },
      { code: 405, description: 'метод не поддерживается' },
      { code: 500, description: 'БД не настроена' }
    ],
    notes: 'Оба поля в теле запроса необязательны и независимы — можно передать только одно.'
  },
  {
    id: 'migrate-user',
    name: 'migrate-user',
    httpMethods: ['POST', 'OPTIONS'],
    description:
      'Переносит анонимного пользователя (случайный user_id, сгенерированный в браузере) на постоянный ID вида ecom_{логин_кассы}, перенося все его настройки и чеки.',
    requestFields: [
      { name: 'old_user_id', type: 'string', required: true, description: 'Старый анонимный ID пользователя' },
      { name: 'ecomkassa_login', type: 'string', required: true, description: 'Логин кассы Ecomkassa' }
    ],
    requestExample: `{ "old_user_id": "user_3lwjqe8wa1tmrbwy1k7", "ecomkassa_login": "sergey" }`,
    responseExample: `{
  "success": true,
  "new_user_id": "ecom_sergey",
  "old_user_id": "user_3lwjqe8wa1tmrbwy1k7",
  "migrated": true,
  "conflict_resolved": false
}`,
    errors: [
      { code: 400, description: 'нет old_user_id/ecomkassa_login' },
      { code: 405, description: 'метод не POST' },
      { code: 500, description: 'БД не настроена' }
    ],
    notes: 'Если new_user_id уже занят, автоматически генерируется вариант с числовым суффиксом (conflict_resolved: true).'
  }
];

export const commonReferences = [
  {
    title: 'Типы платежей (payments[].type)',
    items: [
      '0 — наличные',
      '1 — безнал',
      '2 — предоплата (аванс)',
      '3 — кредит',
      '4 — иная форма',
      '5 — расширенный аванс',
      '6 — расширенный кредит'
    ]
  },
  {
    title: 'Системы налогообложения (sno)',
    items: [
      'osn — ОСН',
      'usn_income — УСН доходы',
      'usn_income_outcome — УСН доходы-расходы',
      'envd — ЕНВД',
      'esn — ЕСН',
      'patent — Патент'
    ]
  },
  {
    title: 'НДС (vat)',
    items: ['none', 'vat0', 'vat10', 'vat20', 'vat110', 'vat120']
  },
  {
    title: 'Предмет расчёта (payment_object)',
    items: ['commodity — товар', 'service — услуга', 'job — работа', 'excise — подакцизный товар', 'и др. — полный список в ATOL Online v5']
  }
];
