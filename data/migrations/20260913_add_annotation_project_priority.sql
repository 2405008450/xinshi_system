BEGIN;

ALTER TABLE annotation_project
    ADD COLUMN IF NOT EXISTS priority VARCHAR(10) NOT NULL DEFAULT 'medium';

ALTER TABLE annotation_project
    DROP CONSTRAINT IF EXISTS ck_annotation_project_priority;

ALTER TABLE annotation_project
    ADD CONSTRAINT ck_annotation_project_priority
    CHECK (priority IN ('low', 'medium', 'high'));

COMMENT ON COLUMN annotation_project.priority IS '优先次序：低、中、高';

COMMIT;
