-- 项目订单号永久占用与改号审计。第一期仅回填标注项目。

DO $$
BEGIN
    IF EXISTS (
        SELECT upper(btrim(order_no))
        FROM annotation_project
        GROUP BY upper(btrim(order_no))
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION '标注项目存在忽略大小写后的重复订单号，无法建立永久占用记录';
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS project_order_no_reservation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_type VARCHAR(30) NOT NULL,
    project_id UUID NOT NULL,
    order_no VARCHAR(80) NOT NULL,
    order_no_key VARCHAR(80) NOT NULL,
    assignment_source VARCHAR(50) NOT NULL,
    assigned_by UUID,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_project_order_no_reservation_actor
        FOREIGN KEY (assigned_by) REFERENCES app_user(id) ON DELETE SET NULL,
    CONSTRAINT ck_project_order_no_reservation_type
        CHECK (project_type IN ('translation','interpretation','annotation','recruitment')),
    CONSTRAINT uq_project_order_no_reservation_type_key
        UNIQUE (project_type, order_no_key)
);

CREATE INDEX IF NOT EXISTS ix_project_order_no_reservation_project
    ON project_order_no_reservation (project_type, project_id, assigned_at);

INSERT INTO project_order_no_reservation (
    project_type, project_id, order_no, order_no_key, assignment_source, assigned_by, assigned_at
)
SELECT
    'annotation', id, btrim(order_no), upper(btrim(order_no)), 'backfill', created_by, created_at
FROM annotation_project
ON CONFLICT (project_type, order_no_key) DO NOTHING;

INSERT INTO project_order_no_reservation (
    project_type, project_id, order_no, order_no_key, assignment_source, assigned_by, assigned_at
)
SELECT DISTINCT ON (upper(btrim(order_no)))
    'annotation', project_id, btrim(order_no), upper(btrim(order_no)),
    'audit_backfill', actor_user_id, occurred_at
FROM project_operation_audit
WHERE project_type = 'annotation' AND btrim(order_no) <> ''
ORDER BY upper(btrim(order_no)), occurred_at ASC
ON CONFLICT (project_type, order_no_key) DO NOTHING;

ALTER TABLE project_operation_audit
    ADD COLUMN IF NOT EXISTS previous_order_no VARCHAR(80);
ALTER TABLE project_operation_audit
    ADD COLUMN IF NOT EXISTS change_reason VARCHAR(500);

ALTER TABLE project_operation_audit
    DROP CONSTRAINT IF EXISTS ck_project_operation_audit_operation;
ALTER TABLE project_operation_audit
    ADD CONSTRAINT ck_project_operation_audit_operation
    CHECK (operation_type IN ('create','delete','order_no_change'));

COMMENT ON TABLE project_order_no_reservation
    IS '项目订单号永久占用记录；订单号改动或项目删除后也不释放';
COMMENT ON COLUMN project_order_no_reservation.order_no_key
    IS '用于唯一性校验的标准化订单号（去除首尾空格并转大写）';
