BEGIN;

ALTER TABLE project_manager_handover_request
    ADD COLUMN IF NOT EXISTS manager_role VARCHAR(30) NOT NULL DEFAULT 'project_manager';

UPDATE project_manager_handover_request
SET manager_role = 'project_manager'
WHERE manager_role IS NULL;

ALTER TABLE project_manager_handover_request
    DROP CONSTRAINT IF EXISTS ck_pm_handover_request_manager_role;

ALTER TABLE project_manager_handover_request
    ADD CONSTRAINT ck_pm_handover_request_manager_role
    CHECK (manager_role IN ('project_manager', 'client_manager'));

ALTER TABLE project_manager_handover_item
    ADD COLUMN IF NOT EXISTS annotation_project_id UUID;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_pm_handover_item_annotation_project'
    ) THEN
        ALTER TABLE project_manager_handover_item
            ADD CONSTRAINT fk_pm_handover_item_annotation_project
            FOREIGN KEY (annotation_project_id)
            REFERENCES annotation_project(id)
            ON DELETE CASCADE;
    END IF;
END $$;

ALTER TABLE project_manager_handover_item
    DROP CONSTRAINT IF EXISTS ck_pm_handover_item_exactly_one_source;

ALTER TABLE project_manager_handover_item
    ADD CONSTRAINT ck_pm_handover_item_exactly_one_source
    CHECK (
        (CASE WHEN translation_project_id IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN project_responsibility_id IS NOT NULL THEN 1 ELSE 0 END) +
        (CASE WHEN annotation_project_id IS NOT NULL THEN 1 ELSE 0 END) = 1
    );

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_pm_handover_item_annotation_project'
    ) THEN
        ALTER TABLE project_manager_handover_item
            ADD CONSTRAINT uq_pm_handover_item_annotation_project
            UNIQUE (request_id, annotation_project_id);
    END IF;
END $$;

COMMIT;
