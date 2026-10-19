-- 仅创建团队会话分类；不修改现有消息主题、权限或历史业务数据。
BEGIN;
CREATE TABLE IF NOT EXISTS chat_session_category (
 id uuid PRIMARY KEY, name varchar(80) NOT NULL CHECK (length(trim(name)) > 0),
 active boolean NOT NULL DEFAULT true, revision integer NOT NULL DEFAULT 1,
 updated_by uuid NOT NULL REFERENCES app_user(id),
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_session_category_name ON chat_session_category(lower(name));
CREATE TABLE IF NOT EXISTS chat_session_category_link (
 id uuid PRIMARY KEY, category_id uuid NOT NULL REFERENCES chat_session_category(id),
 project_id uuid REFERENCES translation_project(id) ON DELETE CASCADE,
 annotation_project_id uuid REFERENCES annotation_project(id) ON DELETE CASCADE,
 direct_conversation_id uuid REFERENCES chat_direct_conversation(id) ON DELETE CASCADE,
 updated_by uuid NOT NULL REFERENCES app_user(id), updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT ck_session_category_one_target CHECK (num_nonnulls(project_id, annotation_project_id, direct_conversation_id) = 1)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_session_category_translation ON chat_session_category_link(category_id, project_id) WHERE project_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_session_category_annotation ON chat_session_category_link(category_id, annotation_project_id) WHERE annotation_project_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_session_category_direct ON chat_session_category_link(category_id, direct_conversation_id) WHERE direct_conversation_id IS NOT NULL;
COMMIT;
