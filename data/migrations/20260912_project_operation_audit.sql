CREATE TABLE IF NOT EXISTS project_operation_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_type VARCHAR(30) NOT NULL,
    project_id UUID NOT NULL,
    order_no VARCHAR(80) NOT NULL,
    project_name VARCHAR(500),
    operation_type VARCHAR(20) NOT NULL,
    operation_source VARCHAR(50) NOT NULL,
    actor_user_id UUID,
    actor_username_snapshot VARCHAR(100),
    actor_name_snapshot VARCHAR(255),
    project_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_project_operation_audit_actor
        FOREIGN KEY (actor_user_id) REFERENCES app_user(id) ON DELETE SET NULL,
    CONSTRAINT ck_project_operation_audit_type
        CHECK (project_type IN ('translation','interpretation','annotation','recruitment')),
    CONSTRAINT ck_project_operation_audit_operation
        CHECK (operation_type IN ('create','delete'))
);

CREATE INDEX IF NOT EXISTS ix_project_operation_audit_order_time
    ON project_operation_audit (order_no, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_project_operation_audit_type_time
    ON project_operation_audit (project_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_project_operation_audit_actor_time
    ON project_operation_audit (actor_user_id, occurred_at DESC);

COMMENT ON TABLE project_operation_audit IS '四类项目新增、删除操作的永久审计记录';
COMMENT ON COLUMN project_operation_audit.project_id IS '项目原始 UUID，仅作快照，不与已删除项目建立外键';
