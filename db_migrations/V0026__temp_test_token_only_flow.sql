INSERT INTO user_settings (user_id, ecomkassa_login, ecomkassa_password, group_code, updated_at)
VALUES ('ecom_test_shop_flow_temp', 'sergey@ecomkassa.ru', '', '', CURRENT_TIMESTAMP)
ON CONFLICT (user_id) DO UPDATE SET group_code = '', ecomkassa_password = '';

INSERT INTO ecomkassa_sessions (token, user_id, expires_at, updated_at)
VALUES ('eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxLTdoM05Sb3RxcmQ4UVorSGVLaDZFSEFTOTZRdXF2Z3VOYnNCeDRiRkQwSVhoczNIWGVaQ3JxUTEyaUdHUFNkcDVrUVlvbVNKTUdZSjFscm9uRm55UzBiY2dPVG5nM3JjaUFGTzBaUGN3NWdVPSIsImlzcyI6ImFwcC5lY29ta2Fzc2EucnUiLCJleHAiOjE3ODc3MjY0OTUsImlhdCI6MTc4NzY0MDA5NSwianRpIjoiM2Y1ODM1MWM3NmI5MzMyNjJkYTVmYTIzMWZiYjA1YWE1M2FmYzRmYjRjZDI5NzBlNDgzZGYwMGM2YTEzYmEzMzlhMjVlNDNiNGZlZGYzNDZhNDA0YTI5ZjBiMDA4MTZiMWY1ZDY2MzA5OTJjMGM2Yjg3NjI3MTczNDMyNDUyZmY0MDM5NzAwZWQ0Y2JkYmI0OWIzZjk4NmI5MjIyOTFlYTliODdkYTNiYWRjNTVkZmJiNDlhMGM4OWVkNWVmZGFhNDg4YjBlZGU1NmUyNzg5OTE3ODAxYTAxOTM2N2IzOTYwMGM3ZDdiNTM0ZTQzMmQ5ZTJkZTRkNmVjYWM1NDVmYSJ9._6oOX1o-GGdqXN2Esq_jPU1Ev-4v7k3tGwm-Y5iQLvs', 'ecom_test_shop_flow_temp', CURRENT_TIMESTAMP + INTERVAL '1 hour', CURRENT_TIMESTAMP)
ON CONFLICT (token) DO UPDATE SET user_id = 'ecom_test_shop_flow_temp', expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour';

INSERT INTO ecomkassa_sessions (token, user_id, expires_at, updated_at)
VALUES ('test-temp-session-token-shop-flow-12345', 'ecom_test_shop_flow_temp', CURRENT_TIMESTAMP - INTERVAL '1 hour', CURRENT_TIMESTAMP)
ON CONFLICT (token) DO UPDATE SET expires_at = CURRENT_TIMESTAMP - INTERVAL '1 hour';