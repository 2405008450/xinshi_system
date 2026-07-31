BEGIN;

ALTER TABLE chat_project_message
    ADD COLUMN IF NOT EXISTS message_type VARCHAR(30) NOT NULL DEFAULT 'user',
    ADD COLUMN IF NOT EXISTS content_json JSONB,
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS chat_project_attachment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploaded_by UUID,
    original_name VARCHAR(255) NOT NULL,
    storage_name VARCHAR(255) NOT NULL UNIQUE,
    content_type VARCHAR(100) NOT NULL,
    file_size BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_chat_attachment_uploader
        FOREIGN KEY (uploaded_by) REFERENCES app_user(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_chat_project_attachment_created_at
    ON chat_project_attachment(created_at);

CREATE TABLE IF NOT EXISTS chat_project_message_attachment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    attachment_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_chat_message_attachment_message
        FOREIGN KEY (message_id) REFERENCES chat_project_message(id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_message_attachment_attachment
        FOREIGN KEY (attachment_id) REFERENCES chat_project_attachment(id) ON DELETE CASCADE,
    CONSTRAINT uq_chat_message_attachment UNIQUE (message_id, attachment_id)
);

CREATE INDEX IF NOT EXISTS ix_chat_message_attachment_attachment_id
    ON chat_project_message_attachment(attachment_id);

COMMIT;
