# API проекта — описание backend-методов

Все методы — Python Cloud Functions (Python 3.11). Актуальные URL — в `backend/func2url.json`.
CORS: все методы поддерживают `OPTIONS` и возвращают заголовок `Access-Control-Allow-Origin: *`.

---

## Оглавление

1. [process-receipt](#1-process-receipt) — создание/предпросмотр чека (главный метод)
2. [ecomkassa-proxy](#2-ecomkassa-proxy) — прямой прокси к кассе Ecomkassa (АТОЛ v5)
3. [get-receipts](#3-get-receipts) — история чеков
4. [user-settings](#4-user-settings) — настройки пользователя (касса, ИНН и т.д.)
5. [ai-settings](#5-ai-settings) — настройки ИИ-провайдера (админ)
6. [admin-auth](#6-admin-auth) — вход в админ-панель
7. [admin-stats](#7-admin-stats) — статистика отзывов (админ)
8. [save-feedback](#8-save-feedback) — сохранение лайка/дизлайка ответа
9. [telegram-bot](#9-telegram-bot) — вебхук Telegram-бота
10. [telegram-link](#10-telegram-link) — привязка Telegram к аккаунту
11. [telegram-token](#11-telegram-token) — токен Telegram-бота (админ)
12. [migrate-user](#12-migrate-user) — перенос анонимного пользователя на постоянный ID

---

## 1. process-receipt

**Назначение:** основной метод. Превращает текст на естественном языке ("Кофе 200₽ безнал") в структуру чека и, если это не предпросмотр — отправляет его в кассу Ecomkassa.

**Метод:** `POST` (+ `OPTIONS`)

**Заголовки:**
| Заголовок | Обязательный | Описание |
|---|---|---|
| `X-User-Id` | нет | ID пользователя — если передан, подтягиваются его сохранённые настройки кассы |

**Тело запроса:**
```json
{
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
  },
  "edited_data": { "...": "отредактированные items/payments, если preview_only=false" },
  "previous_receipt": {},
  "context_message": "текст предыдущего незавершённого запроса"
}
```
| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `message` | string | да | Текст запроса на естественном языке |
| `operation_type` | string | нет | `sell` \| `refund` \| `sell_correction` \| `refund_correction` |
| `preview_only` | boolean | нет | `true` — только распознать и вернуть предпросмотр, ничего не отправляя |
| `document_type` | string | нет | `receipt` (обычный чек) \| `link` (платёжная ссылка) |
| `settings` | object | нет | Данные кассы; если есть `X-User-Id`, дополняются/перекрываются сохранёнными в БД |
| `edited_data` | object | нет | Данные чека после ручного редактирования пользователем (используются вместо результата ИИ) |
| `previous_receipt` | object | нет | Чек из предыдущего шага диалога (для правок/уточнений) |

**Ответ (preview_only=true):**
```json
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
```

**Ответ (preview_only=false, чек отправлен):**
```json
{
  "success": true,
  "uuid": "a1b2c3d4-...",
  "external_id": "AI_1710234567890",
  "permalink": "https://receipts.ecomkassa.ru/...",
  "payment_link": "https://app.ecomkassa.ru/pay/... (только для document_type=link)",
  "qr_code": "data:image/png;base64,... (только если есть payment_link)"
}
```

**Коды ответа / ошибки:**
| Код | Когда |
|---|---|
| 200 | успех (в т.ч. preview) |
| 400 | пустое `message`, слишком короткий запрос без контекста, товар не указан для платёжной ссылки |
| 405 | метод не POST |
| 200 + `success:false` | нераспознанный/нерелевантный текст (приветствие и т.п.) — возвращается подсказка |

**Типы платежей (payments[].type):** `0`=наличные, `1`=безнал, `2`=предоплата, `3`=кредит, `4`=иная форма, `5`/`6`=расширенный аванс/кредит.

---

## 2. ecomkassa-proxy

**Назначение:** низкоуровневый прокси к API кассы Ecomkassa (протокол ATOL Online v5). Сам получает токен по логину/паролю и выполняет запрос к нужному endpoint кассы. Используется внутри `process-receipt`, но доступен и напрямую.

**Метод:** `POST` (+ `OPTIONS`)

**Тело запроса:**
```json
{
  "login": "ecomkassa_login",
  "password": "ecomkassa_password",
  "endpoint": "/fiscalorder/v5/{group_code}/sell",
  "method": "POST",
  "payload": { "...": "тело запроса к кассе (items, payments, client, company)" }
}
```
| Поле | Обязательное | Описание |
|---|---|---|
| `login` / `password` | да | Учётные данные кассы Ecomkassa |
| `endpoint` | нет | По умолчанию `/fiscalorder/v5/default_group/sell` |
| `method` | нет | `GET` или `POST`, по умолчанию `GET` |
| `payload` | нет (обязательно для POST) | Тело запроса к кассе |

**Ответ:** прямой ответ от Ecomkassa (код чека, статус, `uuid`, `invoice_payload` и т.д.), с добавлением поля `qr_code` (base64 PNG), если в ответе присутствует платёжная ссылка `invoice_payload.link`.

**Коды ошибок:**
| Код | Когда |
|---|---|
| 400 | нет login/password, некорректный JSON, неподдерживаемый `method` |
| 401 | неверные учётные данные Ecomkassa |
| 405 | метод не POST |
| 500 | сбой сети/запроса к Ecomkassa |

---

## 3. get-receipts

**Назначение:** история созданных чеков с пагинацией.

**Метод:** `GET` (+ `OPTIONS`)

**Query-параметры:**
| Параметр | По умолчанию | Описание |
|---|---|---|
| `limit` | 50 | Сколько чеков вернуть |
| `offset` | 0 | Смещение для пагинации |

**Ответ:**
```json
{
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
}
```

**Коды ошибок:** `405` метод не GET; `500` БД не настроена / ошибка запроса.

---

## 4. user-settings

**Назначение:** сохранение и загрузка индивидуальных настроек пользователя (данные кассы, ИНН, СНО, ключи ИИ).

**Метод:** `GET`, `POST` (+ `OPTIONS`)

**Заголовки:** `X-User-Id` — **обязателен** для GET и POST.

**Тело запроса (POST):**
```json
{
  "settings": {
    "group_code": "...", "inn": "...", "sno": "usn_income",
    "default_vat": "none", "company_email": "...", "payment_address": "...",
    "ecomkassa_login": "...", "ecomkassa_password": "...",
    "active_ai_provider": "...", "gigachat_auth_key": "...",
    "yandexgpt_api_key": "...", "yandexgpt_folder_id": "...", "gptunnel_api_key": "..."
  }
}
```

**Ответ (GET):**
```json
{ "settings": { "group_code": "", "inn": "", "sno": "usn_income", "default_vat": "none", "...": "..." } }
```

**Ответ (POST):**
```json
{ "status": "saved", "settings": { "...": "то, что сохранено" } }
```

**Коды ошибок:** `400` нет заголовка `X-User-Id`; `405` метод не GET/POST; `500` БД не настроена.

---

## 5. ai-settings

**Назначение:** управление ИИ-провайдером для распознавания текста/голоса на уровне всего проекта (админ-функция). Проверяет валидность ключей перед сохранением.

**Метод:** `GET`, `POST` (+ `OPTIONS`)

**Заголовки:** `X-Admin-Token` — **обязателен**.

**Тело запроса (POST):**
```json
{
  "provider_id": "gptunnel_chatgpt",
  "selected_model": "gpt-4o",
  "gptunnel_api_key": "...",
  "yandex_speechkit_key": "...",
  "disable_type": "text"
}
```
| Поле | Описание |
|---|---|
| `provider_id` | `gptunnel_chatgpt` (текст) \| `yandex_speechkit` (голос) \| пусто (отключить) |
| `selected_model` | ID модели для GPTunnel |
| `disable_type` | `text` или `voice` — что именно отключать, если `provider_id` пуст |

**Ответ (GET):**
```json
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
```

**Ответ (POST):**
```json
{
  "success": true,
  "active_provider": "gptunnel_chatgpt",
  "selected_model": "gpt-4o",
  "validation": { "valid": true, "message": "GPTunnel key and model are valid" }
}
```

**Коды ошибок:** `400` невалидный `provider_id` / отсутствует нужный ключ / ключ не прошёл проверку; `401` нет `X-Admin-Token`; `405`; `500` БД не настроена.

---

## 6. admin-auth

**Назначение:** вход в админ-панель по паролю, выдаёт токен для доступа к `admin-stats`, `ai-settings`, `telegram-token`.

**Метод:** `POST` (+ `OPTIONS`)

**Тело запроса:**
```json
{ "password": "..." }
```

**Ответ:**
```json
{ "token": "sha256-хеш", "expires_in": 86400 }
```

**Коды ошибок:** `401` неверный пароль; `405`; `500` пароль админа не задан на сервере (секрет `ADMIN_PASSWORD`).

---

## 7. admin-stats

**Назначение:** статистика по отзывам пользователей (лайк/дизлайк на ответы ИИ) для админ-панели.

**Метод:** `GET` (+ `OPTIONS`)

**Заголовки:** `X-Admin-Token` — **обязателен**.

**Ответ:**
```json
{
  "total": 40,
  "positive": 35,
  "negative": 5,
  "positive_rate": 87.5,
  "recent_feedback": [
    { "message_id": "...", "user_message": "первые 100 симв.",
      "agent_response": "первые 100 симв.", "feedback_type": "positive",
      "created_at": "2025-12-03T12:31:15" }
  ]
}
```
(отдаёт последние 50 записей)

**Коды ошибок:** `401` нет токена; `405`; `500` БД не настроена.

---

## 8. save-feedback

**Назначение:** сохранение реакции пользователя (👍/👎) на ответ ИИ.

**Метод:** `POST` (+ `OPTIONS`)

**Тело запроса:**
```json
{
  "message_id": "msg_123",
  "user_message": "Создай чек на 100р",
  "agent_response": "Чек создан успешно",
  "feedback_type": "positive"
}
```
| Поле | Обязательное | Описание |
|---|---|---|
| `message_id` | да | ID сообщения |
| `feedback_type` | да | `positive` или `negative` |
| `user_message` / `agent_response` | нет | Текст диалога для контекста |

**Ответ:**
```json
{ "success": true, "message": "Feedback saved successfully" }
```

**Коды ошибок:** `400` нет `message_id`/`feedback_type` или неверное значение `feedback_type`; `405`; `500` БД не настроена / ошибка записи.

---

## 9. telegram-bot

**Назначение:** вебхук для Telegram-бота. Принимает обновления от Telegram (сообщения, голосовые, кнопки), создаёт чеки тем же способом, что и веб-версия, поддерживает команды `/start`, `/help`, `/history`, `/repeat`, повтор по UUID, редактирование через диалог.

**Метод:** `POST` (+ `OPTIONS`) — вызывается самим Telegram, тело — стандартный формат Telegram Update.

**Тело запроса:** JSON от Telegram (`message`, `callback_query` и т.д. — стандартная структура Telegram Bot API).

**Ответ:** всегда `{"ok": true}` — реальный ответ пользователю отправляется отдельным вызовом Telegram API (`sendMessage`) внутри функции.

**Коды ошибок:** `405` метод не POST; `500` токен бота не настроен (секрет).

**Поддерживаемые команды в сообщении:**
| Команда | Действие |
|---|---|
| `/start` или `/start LINK-XXXX` | приветствие / привязка аккаунта по коду |
| `/help` | справка |
| `/history` | последние 10 чеков с кнопками для повтора |
| `/repeat` | повторить последний чек |
| `повтори <id>` | повторить чек по номеру |
| голосовое сообщение | распознаётся через Yandex SpeechKit, дальше как обычный текстовый запрос |

---

## 10. telegram-link

**Назначение:** генерирует одноразовый код для привязки Telegram-аккаунта к текущему пользователю сайта.

**Метод:** `POST` (+ `OPTIONS`)

**Заголовки:** `X-User-Id` — **обязателен**.

**Ответ:**
```json
{
  "link_code": "LINK-Ab12Cd34",
  "bot_url": "https://t.me/ecomkassa_ai_bot?start=LINK-Ab12Cd34",
  "expires_at": "2025-12-04T14:15:00"
}
```
Код действителен 24 часа.

**Коды ошибок:** `400` нет `X-User-Id`; `405`; `500` БД не настроена.

---

## 11. telegram-token

**Назначение:** сохранение/чтение токена Telegram-бота и флага включения уведомлений (админ-функция).

**Метод:** `GET`, `POST` (+ `OPTIONS`)

**Заголовки:** `X-Admin-Token` — **обязателен**.

**Тело запроса (POST):**
```json
{ "token": "123456:ABC-...", "enabled": true }
```
Оба поля необязательны и независимы — можно передать только одно.

**Ответ (GET):**
```json
{ "token": "123456:ABC-...", "enabled": true }
```

**Ответ (POST):**
```json
{ "success": true }
```

**Коды ошибок:** `400` пустой `token` при попытке его установить; `401` нет `X-Admin-Token`; `405`; `500` БД не настроена.

---

## 12. migrate-user

**Назначение:** переносит анонимного пользователя (случайный `user_id`, сгенерированный в браузере) на постоянный ID вида `ecom_{логин_кассы}`, перенося все его настройки и чеки.

**Метод:** `POST` (+ `OPTIONS`)

**Тело запроса:**
```json
{ "old_user_id": "user_3lwjqe8wa1tmrbwy1k7", "ecomkassa_login": "sergey" }
```

**Ответ:**
```json
{
  "success": true,
  "new_user_id": "ecom_sergey",
  "old_user_id": "user_3lwjqe8wa1tmrbwy1k7",
  "migrated": true,
  "conflict_resolved": false
}
```
Если `new_user_id` уже занят другим пользователем, автоматически генерируется вариант с числовым суффиксом (`conflict_resolved: true`).

**Коды ошибок:** `400` нет `old_user_id`/`ecomkassa_login`; `405`; `500` БД не настроена.

---

## Общие справочники значений

**Типы платежей (payments[].type):**
`0` наличные · `1` безнал · `2` предоплата (аванс) · `3` кредит · `4` иная форма · `5` расширенный аванс · `6` расширенный кредит

**Системы налогообложения (sno):**
`osn` ОСН · `usn_income` УСН доходы · `usn_income_outcome` УСН доходы-расходы · `envd` ЕНВД · `esn` ЕСН · `patent` Патент

**НДС (vat):** `none` · `vat0` · `vat10` · `vat20` · `vat110` · `vat120`

**Предмет расчёта (payment_object):** `commodity` товар · `service` услуга · `job` работа · `excise` подакцизный товар и др. (полный список — в ATOL Online v5)
