BEGIN;

ALTER TABLE project_file
    ADD COLUMN IF NOT EXISTS translation_domain_level1 VARCHAR(255),
    ADD COLUMN IF NOT EXISTS translation_domain_level2 VARCHAR(255),
    ADD COLUMN IF NOT EXISTS file_type_secondary VARCHAR(255),
    ADD COLUMN IF NOT EXISTS file_format VARCHAR(100),
    ADD COLUMN IF NOT EXISTS file_attribute_level1 VARCHAR(255),
    ADD COLUMN IF NOT EXISTS file_attribute_level2 VARCHAR(255),
    ADD COLUMN IF NOT EXISTS file_attribute_level3 VARCHAR(255),
    ADD COLUMN IF NOT EXISTS file_difficulty VARCHAR(100);

ALTER TABLE project_file
    ALTER COLUMN file_type TYPE VARCHAR(255);

ALTER TABLE translation_project
    ADD COLUMN IF NOT EXISTS project_contract_type VARCHAR(100),
    ADD COLUMN IF NOT EXISTS project_contract_status VARCHAR(100),
    ADD COLUMN IF NOT EXISTS quotation_required BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS quotation_status VARCHAR(100),
    ADD COLUMN IF NOT EXISTS quotation_path TEXT,
    ADD COLUMN IF NOT EXISTS customer_requirement_professional TEXT,
    ADD COLUMN IF NOT EXISTS customer_requirement_special TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_project_file_translation_domain_levels'
    ) THEN
        ALTER TABLE project_file
            ADD CONSTRAINT ck_project_file_translation_domain_levels
            CHECK (
                translation_domain_level2 IS NULL
                OR translation_domain_level1 IS NOT NULL
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_project_file_type_levels'
    ) THEN
        ALTER TABLE project_file
            ADD CONSTRAINT ck_project_file_type_levels
            CHECK (file_type_secondary IS NULL OR file_type IS NOT NULL);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_project_file_attribute_levels'
    ) THEN
        ALTER TABLE project_file
            ADD CONSTRAINT ck_project_file_attribute_levels
            CHECK (
                (file_attribute_level2 IS NULL OR file_attribute_level1 IS NOT NULL)
                AND (file_attribute_level3 IS NULL OR file_attribute_level2 IS NOT NULL)
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_translation_project_quotation_fields'
    ) THEN
        ALTER TABLE translation_project
            ADD CONSTRAINT ck_translation_project_quotation_fields
            CHECK (
                quotation_required
                OR (quotation_status IS NULL AND quotation_path IS NULL)
            );
    END IF;
END
$$;

COMMIT;
