-- 为标注项目进度全局检索增加时间范围和正文包含匹配索引。
BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS ix_annotation_status_history_effective_search
    ON annotation_project_status_history (effective_on DESC, changed_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS ix_annotation_status_history_change_note_trgm
    ON annotation_project_status_history
    USING GIN (change_note gin_trgm_ops)
    WHERE change_note IS NOT NULL;

COMMIT;
