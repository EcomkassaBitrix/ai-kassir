-- Таблица для хранения кодов привязки Telegram к user_id
CREATE TABLE IF NOT EXISTS telegram_links (
    link_code VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    telegram_chat_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    linked_at TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_telegram_links_user_id ON telegram_links(user_id);
CREATE INDEX idx_telegram_links_telegram_chat_id ON telegram_links(telegram_chat_id);
CREATE INDEX idx_telegram_links_expires_at ON telegram_links(expires_at);
