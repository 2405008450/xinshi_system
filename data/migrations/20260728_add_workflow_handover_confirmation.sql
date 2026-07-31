BEGIN;

CREATE TABLE IF NOT EXISTS workflow_handover_request (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_id UUID,
    target_user_id UUID NOT NULL,
    handover_type VARCHAR(30) NOT NULL,
    reason_detail VARCHAR(500),
    content TEXT NOT NULL DEFAULT '',
    content_json JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    decision_note VARCHAR(500),
    decided_by UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decided_at TIMESTAMP,
    CONSTRAINT fk_wf_handover_requester
        FOREIGN KEY (requester_id) REFERENCES app_user(id) ON DELETE SET NULL,
    CONSTRAINT fk_wf_handover_target
        FOREIGN KEY (target_user_id) REFERENCES app_user(id) ON DELETE CASCADE,
    CONSTRAINT fk_wf_handover_decider
        FOREIGN KEY (decided_by) REFERENCES app_user(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_wf_handover_target_status
    ON workflow_handover_request(target_user_id, status);

CREATE TABLE IF NOT EXISTS workflow_handover_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL,
    workflow_instance_id UUID NOT NULL,
    expected_assignee_id UUID,
    CONSTRAINT fk_wf_handover_item_request
        FOREIGN KEY (request_id) REFERENCES workflow_handover_request(id) ON DELETE CASCADE,
    CONSTRAINT fk_wf_handover_item_instance
        FOREIGN KEY (workflow_instance_id) REFERENCES workflow_instance(id) ON DELETE CASCADE,
    CONSTRAINT fk_wf_handover_item_assignee
        FOREIGN KEY (expected_assignee_id) REFERENCES app_user(id) ON DELETE SET NULL,
    CONSTRAINT uq_wf_handover_item UNIQUE (request_id, workflow_instance_id)
);

CREATE TABLE IF NOT EXISTS workflow_handover_attachment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL,
    attachment_id UUID NOT NULL,
    CONSTRAINT fk_wf_handover_attachment_request
        FOREIGN KEY (request_id) REFERENCES workflow_handover_request(id) ON DELETE CASCADE,
    CONSTRAINT fk_wf_handover_attachment_file
        FOREIGN KEY (attachment_id) REFERENCES chat_project_attachment(id) ON DELETE CASCADE,
    CONSTRAINT uq_wf_handover_attachment UNIQUE (request_id, attachment_id)
);

COMMIT;
