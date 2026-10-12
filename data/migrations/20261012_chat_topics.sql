BEGIN;
CREATE TABLE IF NOT EXISTS chat_topic (
 id uuid PRIMARY KEY, parent_id uuid REFERENCES chat_topic(id), builtin_key varchar(60) UNIQUE,
 kind varchar(20) NOT NULL DEFAULT 'topic' CHECK (kind IN ('topic','annotation')),
 name varchar(80) NOT NULL, description varchar(500) NOT NULL DEFAULT '',
 sort_order integer NOT NULL DEFAULT 0, active boolean NOT NULL DEFAULT true,
 revision integer NOT NULL DEFAULT 1, updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_topic_sibling_name ON chat_topic(COALESCE(parent_id, '00000000-0000-0000-0000-000000000000'::uuid), lower(name));
CREATE TABLE IF NOT EXISTS chat_message_topic (
 message_id uuid PRIMARY KEY REFERENCES chat_project_message(id) ON DELETE CASCADE,
 topic_id uuid REFERENCES chat_topic(id), updated_by uuid NOT NULL REFERENCES app_user(id),
 updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP, revision integer NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_chat_message_topic_topic ON chat_message_topic(topic_id, message_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_translation_chat_client ON chat_project_message(project_id,sender_user_id,client_message_id) WHERE client_message_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS chat_topic_audit (
 id uuid PRIMARY KEY, entity_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES app_user(id),
 action varchar(40) NOT NULL, before json NOT NULL, after json NOT NULL,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO chat_topic(id, builtin_key, kind, name, sort_order) VALUES
 ('00000000-0000-0000-0000-000000001001','annotation','annotation','标注项目',10),
 ('00000000-0000-0000-0000-000000001002','resource-development','topic','资源开拓讨论',20)
ON CONFLICT DO NOTHING;
INSERT INTO chat_topic(id,parent_id,builtin_key,name,description,sort_order) VALUES
 ('00000000-0000-0000-0000-000000001011','00000000-0000-0000-0000-000000001002','platform','平台讨论','关于开拓平台的问题',10),
 ('00000000-0000-0000-0000-000000001012','00000000-0000-0000-0000-000000001002','people','资源讨论','人的问题',20),
 ('00000000-0000-0000-0000-000000001013','00000000-0000-0000-0000-000000001002','wechat','企微管理','企微问题',30),
 ('00000000-0000-0000-0000-000000001014','00000000-0000-0000-0000-000000001002','posting','发布需求','发圈发帖等',40),
 ('00000000-0000-0000-0000-000000001015','00000000-0000-0000-0000-000000001002','university','高校渠道','高校资源开拓渠道',50),
 ('00000000-0000-0000-0000-000000001016','00000000-0000-0000-0000-000000001002','other','其他渠道','其他资源开拓渠道',60)
ON CONFLICT DO NOTHING;
ALTER TABLE resource_development_issue ALTER COLUMN source_message_id DROP NOT NULL;
ALTER TABLE resource_development_issue ALTER COLUMN source_conversation_id DROP NOT NULL;
ALTER TABLE resource_development_issue DROP CONSTRAINT IF EXISTS resource_development_issue_source_type_check;
ALTER TABLE resource_development_issue DROP CONSTRAINT IF EXISTS ck_development_issue_source_type;
ALTER TABLE resource_development_issue ADD CONSTRAINT ck_development_issue_source_type CHECK (source_type IN ('translation','annotation','direct','manual'));
ALTER TABLE resource_development_issue ADD COLUMN IF NOT EXISTS topic_id uuid REFERENCES chat_topic(id);
ALTER TABLE resource_development_issue ADD COLUMN IF NOT EXISTS topic_path varchar(200) NOT NULL DEFAULT '';
ALTER TABLE resource_development_issue ADD COLUMN IF NOT EXISTS client_request_id uuid;
CREATE UNIQUE INDEX IF NOT EXISTS uq_issue_manual_request ON resource_development_issue(collected_by,client_request_id) WHERE client_request_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_issue_topic ON resource_development_issue(topic_id);
COMMIT;
