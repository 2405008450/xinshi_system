ALTER TABLE recruitment_project
    ADD COLUMN IF NOT EXISTS service_fee_multiplier NUMERIC(7, 4);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_recruitment_service_fee_multiplier'
    ) THEN
        ALTER TABLE recruitment_project
            ADD CONSTRAINT ck_recruitment_service_fee_multiplier
            CHECK (service_fee_multiplier IS NULL OR service_fee_multiplier >= 0);
    END IF;
END
$$;
