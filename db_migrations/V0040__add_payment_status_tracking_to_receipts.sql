ALTER TABLE receipts
ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS paid_at TIMESTAMP DEFAULT NULL,
ADD COLUMN IF NOT EXISTS payment_notified BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN receipts.payment_status IS 'Статус платежной ссылки: wait, paid, expired, cancelled (заполняется при опросе Ecomkassa)';
COMMENT ON COLUMN receipts.paid_at IS 'Время подтверждения оплаты по платежной ссылке';
COMMENT ON COLUMN receipts.payment_notified IS 'Отправлено ли уведомление в Telegram об оплате';

CREATE INDEX IF NOT EXISTS idx_receipts_payment_pending ON receipts (payment_status) WHERE payment_status = 'wait';
