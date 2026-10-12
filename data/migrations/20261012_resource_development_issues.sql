BEGIN;
CREATE TABLE IF NOT EXISTS resource_development_issue (
    id uuid PRIMARY KEY,
    category varchar(20) NOT NULL CHECK (category IN ('arrangement','execution','problem','idea')),
    content text NOT NULL,
    remarks text NOT NULL DEFAULT '',
    source_message_id uuid NOT NULL,
    source_type varchar(20) NOT NULL CHECK (source_type IN ('translation','annotation','direct')),
    source_conversation_id uuid NOT NULL,
    source_title varchar(500) NOT NULL,
    source_content text NOT NULL,
    proposer_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
    proposer_name varchar(255) NOT NULL,
    collected_by uuid NOT NULL REFERENCES app_user(id),
    collected_by_name varchar(255) NOT NULL,
    updated_by uuid NOT NULL REFERENCES app_user(id),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revision integer NOT NULL DEFAULT 1,
    CONSTRAINT uq_development_issue_source_category UNIQUE(source_message_id, category)
);
CREATE TABLE IF NOT EXISTS resource_development_issue_task (
    id uuid PRIMARY KEY,
    issue_id uuid NOT NULL REFERENCES resource_development_issue(id) ON DELETE CASCADE,
    content text NOT NULL,
    executor_id uuid NOT NULL REFERENCES app_user(id),
    executor_name varchar(255) NOT NULL,
    planned_date date,
    status varchar(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','cancelled')),
    progress text NOT NULL DEFAULT '',
    completed_date date,
    remarks text NOT NULL DEFAULT '',
    created_by uuid NOT NULL REFERENCES app_user(id),
    updated_by uuid NOT NULL REFERENCES app_user(id),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revision integer NOT NULL DEFAULT 1,
    CHECK ((status = 'completed') = (completed_date IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_development_issue_created ON resource_development_issue(created_at, id);
CREATE INDEX IF NOT EXISTS ix_resource_development_issue_proposer_id ON resource_development_issue(proposer_id);
CREATE INDEX IF NOT EXISTS ix_resource_development_issue_collected_by ON resource_development_issue(collected_by);
CREATE INDEX IF NOT EXISTS ix_resource_development_issue_task_issue_id ON resource_development_issue_task(issue_id);
CREATE INDEX IF NOT EXISTS ix_development_issue_task_executor ON resource_development_issue_task(executor_id, issue_id);
CREATE INDEX IF NOT EXISTS ix_development_issue_task_filter ON resource_development_issue_task(issue_id, status, planned_date);
COMMIT;
