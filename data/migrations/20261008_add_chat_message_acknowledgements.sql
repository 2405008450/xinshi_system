CREATE TABLE IF NOT EXISTS chat_project_message_acknowledgement (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    user_id UUID NOT NULL,
    user_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_chat_project_message_acknowledgement_message
        FOREIGN KEY (message_id) REFERENCES chat_project_message(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_project_message_acknowledgement_user
        FOREIGN KEY (user_id) REFERENCES app_user(id) ON DELETE CASCADE,
    CONSTRAINT uq_chat_project_message_acknowledgement_message_user UNIQUE (message_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_chat_project_message_acknowledgement_message_created_at
    ON chat_project_message_acknowledgement (message_id, created_at);

CREATE INDEX IF NOT EXISTS ix_chat_project_message_acknowledgement_user_id
    ON chat_project_message_acknowledgement (user_id);
