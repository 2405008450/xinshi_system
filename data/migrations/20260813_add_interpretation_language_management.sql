BEGIN;

ALTER TABLE interpretation_language
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE interpretation_language
    ADD COLUMN IF NOT EXISTS updated_by UUID;

ALTER TABLE interpretation_language
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_interpretation_language_updater'
    ) THEN
        ALTER TABLE interpretation_language
            ADD CONSTRAINT fk_interpretation_language_updater
            FOREIGN KEY (updated_by)
            REFERENCES app_user(id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_interpretation_language_active
    ON interpretation_language(is_active);

COMMIT;
