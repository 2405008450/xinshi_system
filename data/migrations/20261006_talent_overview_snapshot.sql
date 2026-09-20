BEGIN;

CREATE TABLE IF NOT EXISTS talent_overview_snapshot (
    id SMALLINT PRIMARY KEY,
    payload JSONB NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    updated_by UUID,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_talent_overview_snapshot_singleton CHECK (id = 1),
    CONSTRAINT ck_talent_overview_snapshot_revision CHECK (revision >= 1),
    CONSTRAINT fk_talent_overview_snapshot_updated_by
        FOREIGN KEY (updated_by) REFERENCES app_user(id) ON DELETE SET NULL
);

COMMIT;
