-- 客户进度与项目状态历史独立；不复制或改写历史项目进度。
BEGIN;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE IF NOT EXISTS annotation_customer_progress (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    change_note text NOT NULL,
    effective_on timestamptz NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by uuid REFERENCES app_user(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by uuid REFERENCES app_user(id) ON DELETE SET NULL,
    CONSTRAINT ck_annotation_customer_progress_note CHECK (length(trim(change_note)) BETWEEN 1 AND 10000)
);
CREATE INDEX IF NOT EXISTS ix_annotation_customer_progress_timeline ON annotation_customer_progress (project_id, effective_on DESC, changed_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_annotation_customer_progress_recent ON annotation_customer_progress (changed_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_annotation_customer_progress_search ON annotation_customer_progress USING gin (change_note gin_trgm_ops);
COMMIT;
