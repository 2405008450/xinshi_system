BEGIN;

ALTER TABLE workflow_handover_request
    ADD COLUMN IF NOT EXISTS transfer_mode VARCHAR(20) NOT NULL DEFAULT 'permanent',
    ADD COLUMN IF NOT EXISTS delegation_end_at TIMESTAMP;

DO $$ BEGIN
    ALTER TABLE workflow_handover_request
        ADD CONSTRAINT ck_wf_handover_transfer_mode
        CHECK (transfer_mode IN ('permanent', 'delegation'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS workflow_task_delegation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    handover_request_id UUID NOT NULL REFERENCES workflow_handover_request(id) ON DELETE CASCADE,
    workflow_instance_id UUID REFERENCES workflow_instance(id) ON DELETE CASCADE,
    project_responsibility_id UUID REFERENCES project_workbench_responsibility(id) ON DELETE CASCADE,
    original_assignee_id UUID NOT NULL REFERENCES app_user(id) ON DELETE RESTRICT,
    delegate_assignee_id UUID NOT NULL REFERENCES app_user(id) ON DELETE RESTRICT,
    planned_end_at TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'returned', 'completed', 'cancelled')),
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    ended_by_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    end_note VARCHAR(500),
    overdue_notified_at TIMESTAMP,
    CONSTRAINT ck_wf_delegation_exactly_one_source CHECK (
        (workflow_instance_id IS NOT NULL AND project_responsibility_id IS NULL)
        OR (workflow_instance_id IS NULL AND project_responsibility_id IS NOT NULL)
    )
);
ALTER TABLE workflow_task_delegation
    ADD COLUMN IF NOT EXISTS overdue_notified_at TIMESTAMP;
CREATE INDEX IF NOT EXISTS ix_wf_delegation_original_status
    ON workflow_task_delegation(original_assignee_id, status);
CREATE INDEX IF NOT EXISTS ix_wf_delegation_delegate_status
    ON workflow_task_delegation(delegate_assignee_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_wf_delegation_active_instance
    ON workflow_task_delegation(workflow_instance_id)
    WHERE status = 'active' AND workflow_instance_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_wf_delegation_active_responsibility
    ON workflow_task_delegation(project_responsibility_id)
    WHERE status = 'active' AND project_responsibility_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS task_activity_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key VARCHAR(255) NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    counterpart_user_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    event_type VARCHAR(30) NOT NULL
        CHECK (event_type IN ('handover_out','handover_in','return_out','return_in')),
    workflow_instance_id UUID REFERENCES workflow_instance(id) ON DELETE CASCADE,
    project_responsibility_id UUID REFERENCES project_workbench_responsibility(id) ON DELETE CASCADE,
    handover_request_id UUID REFERENCES workflow_handover_request(id) ON DELETE SET NULL,
    delegation_id UUID REFERENCES workflow_task_delegation(id) ON DELETE SET NULL,
    task_type VARCHAR(50) NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    display_metadata JSONB,
    occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_task_activity_exactly_one_source CHECK (
        (workflow_instance_id IS NOT NULL AND project_responsibility_id IS NULL)
        OR (workflow_instance_id IS NULL AND project_responsibility_id IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS ix_task_activity_user_occurred
    ON task_activity_event(user_id, occurred_at);

ALTER TABLE daily_report_item DROP CONSTRAINT IF EXISTS ck_daily_report_item_source_type;
ALTER TABLE daily_report_item
    ADD CONSTRAINT ck_daily_report_item_source_type
    CHECK (source_type IN ('project', 'non_project', 'manual', 'system_event'));

COMMIT;
