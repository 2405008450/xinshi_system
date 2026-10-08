-- 渠道与开拓平台共用原记录；不回填未知的历史创建信息。
BEGIN;
ALTER TABLE resource_development_option ADD COLUMN IF NOT EXISTS purpose text NOT NULL DEFAULT '';
ALTER TABLE resource_development_option ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES app_user(id);
ALTER TABLE resource_development_option ADD COLUMN IF NOT EXISTS updated_by uuid REFERENCES app_user(id);
ALTER TABLE resource_development_option ADD COLUMN IF NOT EXISTS created_at timestamp;
ALTER TABLE resource_development_option ADD COLUMN IF NOT EXISTS updated_at timestamp;
CREATE UNIQUE INDEX IF NOT EXISTS uq_resource_channel_name_normalized
 ON resource_development_option (lower(btrim(name))) WHERE kind = 'platform';
CREATE TABLE IF NOT EXISTS resource_development_channel_member (
 platform_id uuid NOT NULL REFERENCES resource_development_option(id) ON DELETE CASCADE,
 user_id uuid NOT NULL REFERENCES app_user(id), role varchar(20) NOT NULL,
 PRIMARY KEY(platform_id, user_id, role),
 CONSTRAINT ck_channel_member_role CHECK (role IN ('maintainer', 'user'))
);
CREATE INDEX IF NOT EXISTS ix_channel_member_user_role ON resource_development_channel_member(user_id, role);
COMMIT;
