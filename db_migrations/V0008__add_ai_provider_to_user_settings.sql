-- Add AI provider settings to user_settings table
ALTER TABLE user_settings 
ADD COLUMN IF NOT EXISTS active_ai_provider VARCHAR(50) DEFAULT '',
ADD COLUMN IF NOT EXISTS gigachat_auth_key TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS yandexgpt_api_key VARCHAR(255) DEFAULT '',
ADD COLUMN IF NOT EXISTS yandexgpt_folder_id VARCHAR(255) DEFAULT '',
ADD COLUMN IF NOT EXISTS gptunnel_api_key VARCHAR(255) DEFAULT '';

COMMENT ON COLUMN user_settings.active_ai_provider IS 'Активный AI провайдер: gigachat, yandexgpt, gptunnel_chatgpt, gptunnel_claude';
COMMENT ON COLUMN user_settings.gigachat_auth_key IS 'Authorization key для GigaChat';
COMMENT ON COLUMN user_settings.yandexgpt_api_key IS 'API ключ YandexGPT';
COMMENT ON COLUMN user_settings.yandexgpt_folder_id IS 'Folder ID для YandexGPT';
COMMENT ON COLUMN user_settings.gptunnel_api_key IS 'API ключ GPT Tunnel';