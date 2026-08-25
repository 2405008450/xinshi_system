BEGIN;

CREATE TABLE IF NOT EXISTS project_workbench_responsibility (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interpretation_project_id UUID,
    annotation_project_id UUID,
    recruitment_project_id UUID,
    role_code VARCHAR(50) NOT NULL,
    assignee_id UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_workbench_resp_interpretation FOREIGN KEY (interpretation_project_id)
        REFERENCES interpretation_project(id) ON DELETE CASCADE,
    CONSTRAINT fk_workbench_resp_annotation FOREIGN KEY (annotation_project_id)
        REFERENCES annotation_project(id) ON DELETE CASCADE,
    CONSTRAINT fk_workbench_resp_recruitment FOREIGN KEY (recruitment_project_id)
        REFERENCES recruitment_project(id) ON DELETE CASCADE,
    CONSTRAINT fk_workbench_resp_assignee FOREIGN KEY (assignee_id)
        REFERENCES app_user(id) ON DELETE SET NULL,
    CONSTRAINT ck_workbench_resp_exactly_one_project CHECK (
        (CASE WHEN interpretation_project_id IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN annotation_project_id IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN recruitment_project_id IS NOT NULL THEN 1 ELSE 0 END) = 1
    ),
    CONSTRAINT ck_workbench_resp_role_code CHECK (
        role_code IN ('project_manager', 'project_specialist', 'project_assistant')
    ),
    CONSTRAINT uq_workbench_resp_interpretation_role UNIQUE (interpretation_project_id, role_code),
    CONSTRAINT uq_workbench_resp_annotation_role UNIQUE (annotation_project_id, role_code),
    CONSTRAINT uq_workbench_resp_recruitment_role UNIQUE (recruitment_project_id, role_code)
);

CREATE INDEX IF NOT EXISTS ix_workbench_resp_assignee
    ON project_workbench_responsibility(assignee_id);
CREATE INDEX IF NOT EXISTS ix_workbench_resp_role_assignee
    ON project_workbench_responsibility(role_code, assignee_id);

INSERT INTO project_workbench_responsibility (interpretation_project_id, role_code)
SELECT project.id, role.role_code
FROM interpretation_project project
CROSS JOIN (VALUES ('project_manager'), ('project_specialist'), ('project_assistant')) role(role_code)
WHERE project.project_status IN ('initial_follow_up', 'in_progress')
ON CONFLICT DO NOTHING;

INSERT INTO project_workbench_responsibility (annotation_project_id, role_code)
SELECT project.id, role.role_code
FROM annotation_project project
CROSS JOIN (VALUES ('project_manager'), ('project_specialist'), ('project_assistant')) role(role_code)
WHERE project.project_status IN ('pending_confirmation', 'trial', 'in_progress', 'client_feedback')
ON CONFLICT DO NOTHING;

INSERT INTO project_workbench_responsibility (recruitment_project_id, role_code)
SELECT project.id, role.role_code
FROM recruitment_project project
CROSS JOIN (VALUES ('project_manager'), ('project_specialist'), ('project_assistant')) role(role_code)
WHERE project.project_status <> 'closed'
ON CONFLICT DO NOTHING;

ALTER TABLE workflow_handover_item
    ADD COLUMN IF NOT EXISTS project_responsibility_id UUID;
ALTER TABLE workflow_handover_item
    ALTER COLUMN workflow_instance_id DROP NOT NULL;
ALTER TABLE workflow_handover_item
    DROP CONSTRAINT IF EXISTS ck_wf_handover_item_exactly_one_source;
ALTER TABLE workflow_handover_item
    ADD CONSTRAINT ck_wf_handover_item_exactly_one_source CHECK (
        (workflow_instance_id IS NOT NULL AND project_responsibility_id IS NULL) OR
        (workflow_instance_id IS NULL AND project_responsibility_id IS NOT NULL)
    );
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_wf_handover_item_responsibility') THEN
        ALTER TABLE workflow_handover_item ADD CONSTRAINT fk_wf_handover_item_responsibility
            FOREIGN KEY (project_responsibility_id) REFERENCES project_workbench_responsibility(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_wf_handover_item_responsibility') THEN
        ALTER TABLE workflow_handover_item ADD CONSTRAINT uq_wf_handover_item_responsibility
            UNIQUE (request_id, project_responsibility_id);
    END IF;
END $$;

ALTER TABLE project_manager_handover_item
    ADD COLUMN IF NOT EXISTS project_responsibility_id UUID;
ALTER TABLE project_manager_handover_item
    ALTER COLUMN translation_project_id DROP NOT NULL;
ALTER TABLE project_manager_handover_item
    DROP CONSTRAINT IF EXISTS ck_pm_handover_item_exactly_one_source;
ALTER TABLE project_manager_handover_item
    ADD CONSTRAINT ck_pm_handover_item_exactly_one_source CHECK (
        (translation_project_id IS NOT NULL AND project_responsibility_id IS NULL) OR
        (translation_project_id IS NULL AND project_responsibility_id IS NOT NULL)
    );
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_pm_handover_item_responsibility') THEN
        ALTER TABLE project_manager_handover_item ADD CONSTRAINT fk_pm_handover_item_responsibility
            FOREIGN KEY (project_responsibility_id) REFERENCES project_workbench_responsibility(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_pm_handover_item_responsibility') THEN
        ALTER TABLE project_manager_handover_item ADD CONSTRAINT uq_pm_handover_item_responsibility
            UNIQUE (request_id, project_responsibility_id);
    END IF;
END $$;

ALTER TABLE work_entry ADD COLUMN IF NOT EXISTS project_responsibility_id UUID;
ALTER TABLE work_entry DROP CONSTRAINT IF EXISTS ck_work_entry_exactly_one_source;
ALTER TABLE work_entry ADD CONSTRAINT ck_work_entry_exactly_one_source CHECK (
    (CASE WHEN workflow_instance_id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN project_responsibility_id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN non_project_task_id IS NOT NULL THEN 1 ELSE 0 END) = 1
);
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_work_entry_project_responsibility') THEN
        ALTER TABLE work_entry ADD CONSTRAINT fk_work_entry_project_responsibility
            FOREIGN KEY (project_responsibility_id) REFERENCES project_workbench_responsibility(id) ON DELETE CASCADE;
    END IF;
END $$;

ALTER TABLE app_notification
    ADD COLUMN IF NOT EXISTS related_project_type VARCHAR(30),
    ADD COLUMN IF NOT EXISTS related_entity_id UUID;
UPDATE app_notification
SET related_project_type = 'translation', related_entity_id = related_project_id
WHERE related_project_id IS NOT NULL AND related_entity_id IS NULL;

COMMIT;
