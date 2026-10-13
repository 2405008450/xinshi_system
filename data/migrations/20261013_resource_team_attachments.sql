-- 团队资料附件显式增量迁移，不接入启动自动建表。
CREATE TABLE IF NOT EXISTS resource_team_attachment (
    id uuid PRIMARY KEY,
    team_id uuid NOT NULL REFERENCES resource_team(id) ON DELETE CASCADE,
    original_name varchar(255) NOT NULL,
    storage_name varchar(255) NOT NULL UNIQUE,
    content_type varchar(255) NOT NULL,
    file_size integer NOT NULL,
    uploaded_by uuid REFERENCES app_user(id) ON DELETE SET NULL,
    uploaded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_resource_team_attachment_size CHECK (file_size > 0 AND file_size <= 20971520)
);
CREATE INDEX IF NOT EXISTS ix_resource_team_attachment_team_time ON resource_team_attachment(team_id, uploaded_at);
