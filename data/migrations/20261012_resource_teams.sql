-- 团队资源显式增量迁移；不接入启动时自动迁移。
CREATE TABLE IF NOT EXISTS resource_team (
    id uuid PRIMARY KEY,
    short_name varchar(100) NOT NULL,
    full_name varchar(255) NOT NULL DEFAULT '',
    team_type varchar(40) NOT NULL,
    introduction text NOT NULL DEFAULT '',
    resource_types jsonb NOT NULL,
    other_resource_description varchar(500) NOT NULL DEFAULT '',
    resource_situation text NOT NULL DEFAULT '',
    remarks text NOT NULL DEFAULT '',
    contact_user_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
    contact_date date,
    follow_up_user_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
    created_by uuid REFERENCES app_user(id) ON DELETE SET NULL,
    updated_by uuid REFERENCES app_user(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revision integer NOT NULL DEFAULT 1,
    CONSTRAINT ck_resource_team_type CHECK (team_type IN ('small_team','medium_large_company','small_medium_company')),
    CONSTRAINT ck_resource_team_resources CHECK (jsonb_typeof(resource_types) = 'array' AND jsonb_array_length(resource_types) BETWEEN 1 AND 5 AND resource_types <@ '["annotation","interpretation","written_translation","full_time","other"]'::jsonb),
    CONSTRAINT ck_resource_team_other CHECK (NOT resource_types ? 'other' OR length(btrim(other_resource_description)) > 0),
    CONSTRAINT ck_resource_team_revision CHECK (revision > 0)
);
CREATE INDEX IF NOT EXISTS ix_resource_team_updated ON resource_team(updated_at, id);
CREATE INDEX IF NOT EXISTS ix_resource_team_short_name ON resource_team(short_name);
CREATE INDEX IF NOT EXISTS ix_resource_team_full_name ON resource_team(full_name);
CREATE INDEX IF NOT EXISTS ix_resource_team_resources ON resource_team USING gin(resource_types);
CREATE INDEX IF NOT EXISTS ix_resource_team_contact_user_id ON resource_team(contact_user_id);
CREATE INDEX IF NOT EXISTS ix_resource_team_follow_up_user_id ON resource_team(follow_up_user_id);
CREATE INDEX IF NOT EXISTS ix_resource_team_contact_date ON resource_team(contact_date);
CREATE TABLE IF NOT EXISTS resource_team_audit (
    id uuid PRIMARY KEY,
    team_id uuid NOT NULL,
    action varchar(20) NOT NULL,
    actor_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
    actor_name varchar(255) NOT NULL,
    before jsonb,
    after jsonb,
    occurred_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_resource_team_audit_entity_time ON resource_team_audit(team_id, occurred_at);
