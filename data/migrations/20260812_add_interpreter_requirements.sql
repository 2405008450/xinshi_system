BEGIN;

ALTER TABLE translator
    ADD COLUMN IF NOT EXISTS interpretation_level VARCHAR(20);

ALTER TABLE interpretation_project
    ADD COLUMN IF NOT EXISTS required_interpreter_count INTEGER,
    ADD COLUMN IF NOT EXISTS required_interpreter_gender VARCHAR(20),
    ADD COLUMN IF NOT EXISTS required_interpretation_level VARCHAR(20),
    ADD COLUMN IF NOT EXISTS interpreter_special_requirements TEXT,
    ADD COLUMN IF NOT EXISTS interpreter_height_requirement VARCHAR(100),
    ADD COLUMN IF NOT EXISTS interpreter_appearance_requirement VARCHAR(255),
    ADD COLUMN IF NOT EXISTS interpreter_dress_requirement VARCHAR(255);

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_interpretation_required_interpreter_count'
    ) THEN
        ALTER TABLE interpretation_project
            ADD CONSTRAINT ck_interpretation_required_interpreter_count
            CHECK (required_interpreter_count IS NULL OR required_interpreter_count >= 0);
    END IF;
END $$;

COMMIT;
