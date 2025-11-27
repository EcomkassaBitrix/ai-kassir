-- Добавляем отдельные поля для текстового и голосового провайдеров
ALTER TABLE ai_settings ADD COLUMN text_provider VARCHAR(50);
ALTER TABLE ai_settings ADD COLUMN voice_provider VARCHAR(50);

-- Мигрируем данные из старого поля
UPDATE ai_settings 
SET text_provider = CASE 
    WHEN active_provider = 'gptunnel_chatgpt' THEN active_provider 
    ELSE '' 
END,
voice_provider = CASE 
    WHEN active_provider = 'yandex_speechkit' THEN active_provider 
    ELSE '' 
END;

-- Устанавливаем значения по умолчанию для новых записей
ALTER TABLE ai_settings ALTER COLUMN text_provider SET DEFAULT '';
ALTER TABLE ai_settings ALTER COLUMN voice_provider SET DEFAULT '';