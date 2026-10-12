-- 只增加归属关系，不修改、合并或删除已有平台账号与业务记录。
CREATE TABLE IF NOT EXISTS resource_channel_account_link (
 account_id uuid PRIMARY KEY REFERENCES resource_development_option(id) ON DELETE RESTRICT,
 parent_id uuid NOT NULL REFERENCES resource_development_option(id) ON DELETE RESTRICT,
 CONSTRAINT ck_channel_account_not_self CHECK (parent_id <> account_id)
);
CREATE INDEX IF NOT EXISTS ix_channel_account_parent ON resource_channel_account_link(parent_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_resource_channel_group_name_normalized
 ON resource_development_option (lower(btrim(name))) WHERE kind = 'channel_group';
