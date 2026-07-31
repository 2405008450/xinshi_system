BEGIN;

ALTER TABLE project_file
    ADD COLUMN IF NOT EXISTS translator_return_path TEXT,
    ADD COLUMN IF NOT EXISTS project_feedback_path TEXT,
    ADD COLUMN IF NOT EXISTS feedback_delivery_path TEXT;

COMMIT;
