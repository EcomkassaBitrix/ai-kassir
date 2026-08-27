ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS ecomkassa_firm_id VARCHAR(64);
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS ecomkassa_tax_identity VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_user_settings_firm_id ON user_settings (ecomkassa_firm_id);
