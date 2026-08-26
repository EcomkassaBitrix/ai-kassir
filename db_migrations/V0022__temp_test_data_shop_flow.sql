INSERT INTO user_settings (user_id, ecomkassa_login, ecomkassa_password, group_code, updated_at)
VALUES ('ecom_test_shop_flow_temp', 'sergey@ecomkassa.ru', 'ecomkassa', '', CURRENT_TIMESTAMP)
ON CONFLICT (user_id) DO UPDATE SET group_code = '';

INSERT INTO ecomkassa_sessions (token, user_id, expires_at, updated_at)
VALUES ('test-temp-session-token-shop-flow-12345', 'ecom_test_shop_flow_temp', CURRENT_TIMESTAMP + INTERVAL '1 hour', CURRENT_TIMESTAMP)
ON CONFLICT (token) DO UPDATE SET expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour';