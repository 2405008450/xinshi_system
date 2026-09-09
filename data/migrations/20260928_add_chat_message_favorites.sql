CREATE TABLE IF NOT EXISTS chat_project_message_favorite (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    user_id UUID NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_chat_project_message_favorite_message
        FOREIGN KEY (message_id) REFERENCES chat_project_message(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_project_message_favorite_user
        FOREIGN KEY (user_id) REFERENCES app_user(id) ON DELETE CASCADE,
    CONSTRAINT uq_chat_project_message_favorite_message_user UNIQUE (message_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_chat_project_message_favorite_user_created_at
    ON chat_project_message_favorite (user_id, created_at);

CREATE INDEX IF NOT EXISTS ix_chat_project_message_favorite_message_id
    ON chat_project_message_favorite (message_id);
