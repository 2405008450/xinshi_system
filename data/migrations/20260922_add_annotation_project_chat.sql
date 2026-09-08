-- 标注项目复用项目沟通消息表；笔译项目现有数据和接口保持不变。
ALTER TABLE chat_project_message
    ADD COLUMN IF NOT EXISTS annotation_project_id UUID;

ALTER TABLE chat_project_message
    ALTER COLUMN project_id DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_chat_project_message_annotation_project'
    ) THEN
        ALTER TABLE chat_project_message
            ADD CONSTRAINT fk_chat_project_message_annotation_project
            FOREIGN KEY (annotation_project_id)
            REFERENCES annotation_project(id)
            ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_chat_project_message_exactly_one_project'
    ) THEN
        ALTER TABLE chat_project_message
            ADD CONSTRAINT ck_chat_project_message_exactly_one_project
            CHECK (
                (CASE WHEN project_id IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN annotation_project_id IS NOT NULL THEN 1 ELSE 0 END) = 1
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_chat_project_message_annotation_created_at
    ON chat_project_message(annotation_project_id, created_at);
