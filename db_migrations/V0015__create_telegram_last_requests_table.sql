-- Create table for storing last successful requests per chat
CREATE TABLE IF NOT EXISTS telegram_last_requests (
    chat_id BIGINT PRIMARY KEY,
    preview_id TEXT NOT NULL,
    preview_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_telegram_last_requests_created_at 
ON telegram_last_requests(created_at DESC);

-- Add comment
COMMENT ON TABLE telegram_last_requests IS 'Stores last successful receipt request per Telegram chat for /repeat command';