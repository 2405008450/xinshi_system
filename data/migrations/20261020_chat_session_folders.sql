-- 显式执行；不自动迁移，不写入种子分类、不修改消息或现有会话关联。
BEGIN;
CREATE TABLE IF NOT EXISTS chat_session_category_folder (
    category_id uuid PRIMARY KEY REFERENCES chat_session_category(id),
    parent_key varchar(36)
);
CREATE INDEX IF NOT EXISTS ix_chat_session_category_folder_parent
    ON chat_session_category_folder(parent_key);
COMMIT;
