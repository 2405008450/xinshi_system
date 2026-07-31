BEGIN;

ALTER TABLE translation_project
    ADD COLUMN IF NOT EXISTS project_manager_id UUID;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_translation_project_manager'
    ) THEN
        ALTER TABLE translation_project
            ADD CONSTRAINT fk_translation_project_manager
            FOREIGN KEY (project_manager_id)
            REFERENCES app_user(id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_translation_project_manager_id
    ON translation_project(project_manager_id);

CREATE TABLE IF NOT EXISTS project_manager_handover_request (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    target_manager_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    reason VARCHAR(500),
    note TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    decision_note VARCHAR(500),
    decided_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decided_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_pm_handover_target_status
    ON project_manager_handover_request(target_manager_id, status);

CREATE TABLE IF NOT EXISTS project_manager_handover_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES project_manager_handover_request(id) ON DELETE CASCADE,
    translation_project_id UUID NOT NULL REFERENCES translation_project(id) ON DELETE CASCADE,
    expected_manager_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    CONSTRAINT uq_pm_handover_item UNIQUE (request_id, translation_project_id)
);

COMMIT;
