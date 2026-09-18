BEGIN;

ALTER TABLE manuscript_arrangement
    ADD COLUMN IF NOT EXISTS reassigned_from_arrangement_id UUID,
    ADD COLUMN IF NOT EXISTS reassignment_reason VARCHAR(500),
    ADD COLUMN IF NOT EXISTS reassigned_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS reassigned_by UUID,
    ADD COLUMN IF NOT EXISTS reassigned_by_name VARCHAR(255);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_manuscript_arrangement_reassigned_from'
    ) THEN
        ALTER TABLE manuscript_arrangement
            ADD CONSTRAINT fk_manuscript_arrangement_reassigned_from
            FOREIGN KEY (reassigned_from_arrangement_id)
            REFERENCES manuscript_arrangement(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_manuscript_arrangement_reassigned_by'
    ) THEN
        ALTER TABLE manuscript_arrangement
            ADD CONSTRAINT fk_manuscript_arrangement_reassigned_by
            FOREIGN KEY (reassigned_by)
            REFERENCES app_user(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_manuscript_arrangement_reassigned_from'
    ) THEN
        ALTER TABLE manuscript_arrangement
            ADD CONSTRAINT uq_manuscript_arrangement_reassigned_from
            UNIQUE (reassigned_from_arrangement_id);
    END IF;
END $$;

ALTER TABLE manuscript_arrangement
    DROP CONSTRAINT IF EXISTS uq_manuscript_arrangement_dispatch_translator;

CREATE UNIQUE INDEX IF NOT EXISTS uq_manuscript_arrangement_active_dispatch_translator
    ON manuscript_arrangement(dispatch_id, translator_id)
    WHERE status <> 'cancelled';

COMMENT ON COLUMN manuscript_arrangement.reassigned_from_arrangement_id
    IS '改派来源明细；为空表示普通派稿或改派链起点';
COMMENT ON COLUMN manuscript_arrangement.reassignment_reason
    IS '从原译员改派到当前译员的原因';
COMMENT ON COLUMN manuscript_arrangement.reassigned_at
    IS '改派操作时间';

COMMIT;
