BEGIN;

CREATE TABLE IF NOT EXISTS annotation_arrangement_daily_note (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_date DATE NOT NULL,
    content_json JSONB NOT NULL,
    updated_by UUID,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_annotation_arrangement_daily_note_date UNIQUE (note_date),
    CONSTRAINT fk_annotation_arrangement_daily_note_updated_by
        FOREIGN KEY (updated_by) REFERENCES app_user(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_annotation_arrangement_daily_note_date
    ON annotation_arrangement_daily_note (note_date DESC);

COMMIT;
