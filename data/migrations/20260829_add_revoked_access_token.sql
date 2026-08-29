CREATE TABLE IF NOT EXISTS revoked_access_token (
    jti_hash VARCHAR(64) PRIMARY KEY,
    user_id UUID NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_revoked_access_token_expires_at
    ON revoked_access_token (expires_at);
