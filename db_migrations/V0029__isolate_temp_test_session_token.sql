UPDATE ecomkassa_sessions SET expires_at = CURRENT_TIMESTAMP - INTERVAL '1 hour'
WHERE token = 'test-temp-session-token-shop-flow-12345';

INSERT INTO ecomkassa_sessions (token, user_id, expires_at, updated_at)
VALUES ('temp-test-token-2-for-shop-flow', 'ecom_test_shop_flow_temp', CURRENT_TIMESTAMP + INTERVAL '1 hour', CURRENT_TIMESTAMP)
ON CONFLICT (token) DO UPDATE SET expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour';