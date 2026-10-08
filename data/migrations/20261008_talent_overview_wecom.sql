BEGIN;

CREATE TABLE IF NOT EXISTS talent_overview_language_management (
    overview_key VARCHAR(80) PRIMARY KEY,
    plan TEXT NOT NULL DEFAULT '', remarks TEXT NOT NULL DEFAULT '',
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 0),
    operator_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    operator_name VARCHAR(255) NOT NULL, operated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS talent_overview_wecom_group (
    id UUID PRIMARY KEY, overview_key VARCHAR(80) NOT NULL,
    name VARCHAR(200) NOT NULL, is_built BOOLEAN NOT NULL, built_date DATE,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    plan TEXT NOT NULL DEFAULT '', remarks TEXT NOT NULL DEFAULT '',
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    operator_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    operator_name VARCHAR(255) NOT NULL, operated_at TIMESTAMPTZ NOT NULL,
    CHECK (is_built OR built_date IS NULL)
);
CREATE INDEX IF NOT EXISTS ix_overview_wecom_group_language ON talent_overview_wecom_group(overview_key, archived);
CREATE TABLE IF NOT EXISTS talent_overview_wecom_count (
    id BIGSERIAL PRIMARY KEY,
    group_id UUID NOT NULL REFERENCES talent_overview_wecom_group(id),
    statistics_date DATE NOT NULL, people_count INTEGER NOT NULL CHECK (people_count >= 0),
    operator_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    operator_name VARCHAR(255) NOT NULL, operated_at TIMESTAMPTZ NOT NULL,
    voided_at TIMESTAMPTZ, voided_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    voided_by_name VARCHAR(255), void_reason TEXT
);
CREATE INDEX IF NOT EXISTS ix_overview_wecom_count_latest ON talent_overview_wecom_count(group_id, statistics_date, id);
CREATE TABLE IF NOT EXISTS talent_overview_management_audit (
    id BIGSERIAL PRIMARY KEY, overview_key VARCHAR(80) NOT NULL,
    group_id UUID REFERENCES talent_overview_wecom_group(id), operation VARCHAR(30) NOT NULL,
    before JSONB NOT NULL, after JSONB NOT NULL,
    operator_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    operator_name VARCHAR(255) NOT NULL, operated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_overview_management_audit_language ON talent_overview_management_audit(overview_key, id);
CREATE INDEX IF NOT EXISTS ix_overview_management_audit_group ON talent_overview_management_audit(group_id, id);

COMMIT;
