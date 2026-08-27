ALTER TABLE annotation_platform_account
    ADD COLUMN IF NOT EXISTS owner_id UUID;

UPDATE annotation_platform_account
SET owner_id = created_by
WHERE owner_id IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_annotation_account_owner'
    ) THEN
        ALTER TABLE annotation_platform_account
            ADD CONSTRAINT fk_annotation_account_owner
            FOREIGN KEY (owner_id) REFERENCES app_user(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_annotation_account_owner
    ON annotation_platform_account(owner_id);
