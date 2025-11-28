-- Add test user for Telegram ID 265009146
INSERT INTO t_p7891941_voice_ai_agent_1.telegram_users (telegram_lookup_id, user_id)
VALUES ('telegram_265009146', 'ecom_sergey@ecomkassa.ru')
ON CONFLICT (telegram_lookup_id) DO NOTHING;