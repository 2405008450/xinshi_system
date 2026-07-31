BEGIN;

CREATE TABLE IF NOT EXISTS non_project_task_recurrence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(50) NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    assigner_id UUID NOT NULL REFERENCES app_user(id) ON DELETE RESTRICT,
    assignee_id UUID NOT NULL REFERENCES app_user(id) ON DELETE RESTRICT,
    frequency VARCHAR(20) NOT NULL CHECK (frequency IN ('daily', 'workday', 'weekly', 'monthly')),
    weekdays JSONB,
    month_day INTEGER,
    default_due_time TIME,
    start_date DATE NOT NULL,
    end_date DATE,
    remark TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS non_project_task (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(50) NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    assigner_id UUID NOT NULL REFERENCES app_user(id) ON DELETE RESTRICT,
    assignee_id UUID NOT NULL REFERENCES app_user(id) ON DELETE RESTRICT,
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    planned_completion_at TIMESTAMP,
    actual_completion_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    remark TEXT,
    recurrence_template_id UUID REFERENCES non_project_task_recurrence(id) ON DELETE SET NULL,
    occurrence_date DATE,
    source_key VARCHAR(128) UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_non_project_task_recurrence_occurrence
        UNIQUE (recurrence_template_id, occurrence_date)
);
CREATE INDEX IF NOT EXISTS ix_non_project_task_assignee_status
    ON non_project_task(assignee_id, status);
CREATE INDEX IF NOT EXISTS ix_non_project_task_planned_completion
    ON non_project_task(planned_completion_at);

CREATE TABLE IF NOT EXISTS non_project_task_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES non_project_task(id) ON DELETE CASCADE,
    operator_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    event_type VARCHAR(30) NOT NULL,
    from_status VARCHAR(20),
    to_status VARCHAR(20),
    detail JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_non_project_task_event_task_created
    ON non_project_task_event(task_id, created_at);

CREATE TABLE IF NOT EXISTS work_entry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    work_date DATE NOT NULL,
    workflow_instance_id UUID REFERENCES workflow_instance(id) ON DELETE CASCADE,
    non_project_task_id UUID REFERENCES non_project_task(id) ON DELETE CASCADE,
    progress_content TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 0 CHECK (duration_minutes >= 0),
    result_content TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_work_entry_exactly_one_source CHECK (
        (workflow_instance_id IS NOT NULL AND non_project_task_id IS NULL)
        OR (workflow_instance_id IS NULL AND non_project_task_id IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS ix_work_entry_user_date ON work_entry(user_id, work_date);

CREATE TABLE IF NOT EXISTS daily_report (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'finalized')),
    supplemental_note TEXT,
    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finalized_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_daily_report_user_date UNIQUE(user_id, report_date)
);
CREATE INDEX IF NOT EXISTS ix_daily_report_user_date ON daily_report(user_id, report_date);

CREATE TABLE IF NOT EXISTS daily_report_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES daily_report(id) ON DELETE CASCADE,
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('project', 'non_project', 'manual')),
    source_id UUID,
    task_type VARCHAR(50) NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    progress_content TEXT NOT NULL,
    result_content TEXT,
    duration_minutes INTEGER NOT NULL DEFAULT 0,
    display_metadata JSONB,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO role_permission(role_id, permission_code)
SELECT r.id, p.permission_code
FROM role r
CROSS JOIN (
    VALUES ('tasks:read'), ('tasks:self_write'), ('reports:read'), ('reports:export')
) AS p(permission_code)
WHERE r.role_name NOT IN ('admin', '超级管理员')
ON CONFLICT DO NOTHING;

INSERT INTO role_permission(role_id, permission_code)
SELECT r.id, 'tasks:assign'
FROM role r
WHERE r.role_name = '项目经理'
ON CONFLICT DO NOTHING;

COMMIT;
