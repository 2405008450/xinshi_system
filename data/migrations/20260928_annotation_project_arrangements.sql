-- 标注项目“项目安排”：任务类型、安排明细及可编辑具体进度元数据。

CREATE TABLE IF NOT EXISTS annotation_arrangement_task_type (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL,
    normalized_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_annotation_arrangement_task_type_normalized UNIQUE (normalized_name)
);

CREATE INDEX IF NOT EXISTS ix_annotation_arrangement_task_type_active
    ON annotation_arrangement_task_type (is_active);

CREATE TABLE IF NOT EXISTS annotation_project_arrangement_task (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    execution_date DATE NOT NULL,
    task_type_id UUID NOT NULL REFERENCES annotation_arrangement_task_type(id) ON DELETE RESTRICT,
    assignee_id UUID NOT NULL REFERENCES app_user(id) ON DELETE RESTRICT,
    task_content TEXT NOT NULL,
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_annotation_arrangement_task_project_date
    ON annotation_project_arrangement_task (project_id, execution_date);
CREATE INDEX IF NOT EXISTS ix_annotation_arrangement_task_assignee_date
    ON annotation_project_arrangement_task (assignee_id, execution_date);

ALTER TABLE annotation_project_status_history
    ADD COLUMN IF NOT EXISTS entry_kind VARCHAR(20),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_by UUID;

UPDATE annotation_project_status_history
SET entry_kind = CASE WHEN from_status = to_status THEN 'progress' ELSE 'status' END
WHERE entry_kind IS NULL;

UPDATE annotation_project_status_history
SET updated_at = changed_at
WHERE updated_at IS NULL;

ALTER TABLE annotation_project_status_history
    ALTER COLUMN entry_kind SET DEFAULT 'status',
    ALTER COLUMN entry_kind SET NOT NULL,
    ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP,
    ALTER COLUMN updated_at SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_annotation_status_history_entry_kind'
    ) THEN
        ALTER TABLE annotation_project_status_history
            ADD CONSTRAINT ck_annotation_status_history_entry_kind
            CHECK (entry_kind IN ('status', 'progress'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_annotation_status_history_updated_by'
    ) THEN
        ALTER TABLE annotation_project_status_history
            ADD CONSTRAINT fk_annotation_status_history_updated_by
            FOREIGN KEY (updated_by) REFERENCES app_user(id) ON DELETE SET NULL;
    END IF;
END $$;
