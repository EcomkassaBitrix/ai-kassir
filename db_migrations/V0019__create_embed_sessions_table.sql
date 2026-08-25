CREATE TABLE IF NOT EXISTS embed_sessions (
    token VARCHAR(64) NOT NULL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    partner_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_embed_sessions_expires ON embed_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_embed_sessions_user ON embed_sessions(user_id);
