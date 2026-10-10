-- 第一阶段聊天；仅通过显式迁移入口执行，不接入常驻服务启动迁移。
CREATE TABLE IF NOT EXISTS chat_direct_conversation (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 user_low_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
 user_high_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_message_at TIMESTAMPTZ,
 CONSTRAINT uq_chat_direct_pair UNIQUE(user_low_id,user_high_id),
 CONSTRAINT ck_chat_direct_pair_order CHECK(user_low_id < user_high_id)
);
CREATE TABLE IF NOT EXISTS chat_direct_member (
 conversation_id UUID NOT NULL REFERENCES chat_direct_conversation(id) ON DELETE CASCADE,
 user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
 last_read_sequence BIGINT NOT NULL DEFAULT 0,
 pinned BOOLEAN NOT NULL DEFAULT FALSE, starred BOOLEAN NOT NULL DEFAULT FALSE,
 muted BOOLEAN NOT NULL DEFAULT FALSE, hidden_at TIMESTAMPTZ,
 PRIMARY KEY(conversation_id,user_id)
);
CREATE TABLE IF NOT EXISTS chat_project_member_pref (
 project_id UUID NOT NULL REFERENCES translation_project(id) ON DELETE CASCADE,
 user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
 last_read_sequence BIGINT NOT NULL DEFAULT 0,
 pinned BOOLEAN NOT NULL DEFAULT FALSE, starred BOOLEAN NOT NULL DEFAULT FALSE,
 PRIMARY KEY(project_id,user_id)
);
ALTER TABLE annotation_chat_member ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE annotation_chat_member ADD COLUMN IF NOT EXISTS starred BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE chat_project_message ADD COLUMN IF NOT EXISTS direct_conversation_id UUID REFERENCES chat_direct_conversation(id) ON DELETE CASCADE;
ALTER TABLE chat_project_attachment ADD COLUMN IF NOT EXISTS direct_conversation_id UUID REFERENCES chat_direct_conversation(id) ON DELETE CASCADE;
ALTER TABLE chat_project_message DROP CONSTRAINT IF EXISTS ck_chat_project_message_exactly_one_project;
ALTER TABLE chat_project_message ADD CONSTRAINT ck_chat_project_message_exactly_one_project CHECK(num_nonnulls(project_id, annotation_project_id, direct_conversation_id)=1);
CREATE UNIQUE INDEX IF NOT EXISTS uq_direct_chat_client ON chat_project_message(direct_conversation_id,sender_user_id,client_message_id) WHERE client_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_direct_chat_sequence ON chat_project_message(direct_conversation_id,sequence_no);
CREATE INDEX IF NOT EXISTS ix_direct_member_user ON chat_direct_member(user_id);
CREATE TABLE IF NOT EXISTS chat_mention_notification_target (
 notification_id UUID PRIMARY KEY REFERENCES app_notification(id) ON DELETE CASCADE,
 message_id UUID NOT NULL REFERENCES chat_project_message(id) ON DELETE CASCADE
);
