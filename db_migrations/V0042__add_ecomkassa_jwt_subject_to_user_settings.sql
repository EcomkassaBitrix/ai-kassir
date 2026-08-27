ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS ecomkassa_jwt_subject VARCHAR(500);
CREATE INDEX IF NOT EXISTS idx_user_settings_jwt_subject ON user_settings (ecomkassa_jwt_subject);
