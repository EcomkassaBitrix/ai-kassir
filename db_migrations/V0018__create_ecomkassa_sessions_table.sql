CREATE TABLE IF NOT EXISTS t_p7891941_voice_ai_agent_1.ecomkassa_sessions (
    id SERIAL PRIMARY KEY,
    token VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ecomkassa_sessions_token ON t_p7891941_voice_ai_agent_1.ecomkassa_sessions(token);
CREATE INDEX idx_ecomkassa_sessions_user_id ON t_p7891941_voice_ai_agent_1.ecomkassa_sessions(user_id);

COMMENT ON TABLE t_p7891941_voice_ai_agent_1.ecomkassa_sessions IS 'Связка токена Ecomkassa с user_id для мобильного приложения';
COMMENT ON COLUMN t_p7891941_voice_ai_agent_1.ecomkassa_sessions.token IS 'Текущий актуальный токен Ecomkassa для этого пользователя';
COMMENT ON COLUMN t_p7891941_voice_ai_agent_1.ecomkassa_sessions.user_id IS 'Канонический user_id формата ecom_{login}';
COMMENT ON COLUMN t_p7891941_voice_ai_agent_1.ecomkassa_sessions.expires_at IS 'Момент истечения токена (обычно +24ч от выдачи)';
