INSERT INTO user_settings (user_id, ecomkassa_login, ecomkassa_password, group_code, updated_at)
VALUES ('ecom_test_visual_demo', 'sergey@ecomkassa.ru', '', '', CURRENT_TIMESTAMP)
ON CONFLICT (user_id) DO UPDATE SET group_code = '', ecomkassa_password = '';

INSERT INTO ecomkassa_sessions (token, user_id, expires_at, updated_at)
VALUES ('demo-visual-test-token-99887766', 'ecom_test_visual_demo', CURRENT_TIMESTAMP + INTERVAL '1 hour', CURRENT_TIMESTAMP)
ON CONFLICT (token) DO UPDATE SET user_id = 'ecom_test_visual_demo', expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour';