-- 开放项目群：增量、可重复执行；仅首次运行初始化历史未读基线。
CREATE SEQUENCE IF NOT EXISTS chat_message_sequence;
DO $$ BEGIN
IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chat_project_message' AND column_name='sequence_no') THEN
    ALTER TABLE chat_project_message ADD COLUMN sequence_no BIGINT;
    WITH ordered AS (SELECT id,ROW_NUMBER() OVER (ORDER BY created_at,id) AS seq FROM chat_project_message)
    UPDATE chat_project_message m SET sequence_no=ordered.seq FROM ordered WHERE m.id=ordered.id;
    PERFORM setval('chat_message_sequence', COALESCE((SELECT MAX(sequence_no) FROM chat_project_message),0)+1, false);
    ALTER TABLE chat_project_message ALTER COLUMN sequence_no SET DEFAULT nextval('chat_message_sequence');
    ALTER TABLE chat_project_message ALTER COLUMN sequence_no SET NOT NULL;
END IF;
END $$;
ALTER TABLE chat_project_attachment ADD COLUMN IF NOT EXISTS annotation_project_id UUID REFERENCES annotation_project(id) ON DELETE CASCADE;
ALTER TABLE chat_project_message ADD COLUMN IF NOT EXISTS client_message_id UUID;
ALTER TABLE chat_project_message ADD COLUMN IF NOT EXISTS reply_to_message_id UUID REFERENCES chat_project_message(id) ON DELETE SET NULL;
ALTER TABLE chat_project_message ADD COLUMN IF NOT EXISTS recalled_at TIMESTAMP;
ALTER TABLE chat_project_message ADD COLUMN IF NOT EXISTS recalled_by UUID REFERENCES app_user(id) ON DELETE SET NULL;
ALTER TABLE chat_project_message ADD COLUMN IF NOT EXISTS recall_label VARCHAR(500);
CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_sequence ON chat_project_message(sequence_no);
CREATE UNIQUE INDEX IF NOT EXISTS uq_annotation_chat_client ON chat_project_message(annotation_project_id, sender_user_id, client_message_id) WHERE client_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_annotation_chat_sequence ON chat_project_message(annotation_project_id, sequence_no);
CREATE TABLE IF NOT EXISTS annotation_chat_member (
    project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    following BOOLEAN NOT NULL DEFAULT TRUE,
    explicit_unfollow BOOLEAN NOT NULL DEFAULT FALSE,
    last_read_sequence BIGINT NOT NULL DEFAULT 0,
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(project_id,user_id)
);
CREATE INDEX IF NOT EXISTS ix_annotation_chat_member_user ON annotation_chat_member(user_id, following);
INSERT INTO annotation_chat_member(project_id,user_id,last_read_sequence)
SELECT candidates.project_id, candidates.user_id, COALESCE((SELECT MAX(m.sequence_no) FROM chat_project_message m WHERE m.annotation_project_id=candidates.project_id),0)
FROM (
    SELECT id AS project_id,created_by AS user_id FROM annotation_project
    UNION SELECT id,client_manager_id FROM annotation_project
    UNION SELECT annotation_project_id,assignee_id FROM project_workbench_responsibility WHERE annotation_project_id IS NOT NULL
    UNION SELECT annotation_project_id,sender_user_id FROM chat_project_message WHERE annotation_project_id IS NOT NULL
) candidates JOIN app_user u ON u.id=candidates.user_id
WHERE candidates.user_id IS NOT NULL
ON CONFLICT DO NOTHING;
