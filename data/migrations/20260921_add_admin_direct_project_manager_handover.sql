BEGIN;

ALTER TABLE project_manager_handover_request
    ADD COLUMN IF NOT EXISTS handover_mode VARCHAR(20) NOT NULL DEFAULT 'approval';

UPDATE project_manager_handover_request
SET handover_mode = 'approval'
WHERE handover_mode IS NULL;

ALTER TABLE project_manager_handover_request
    DROP CONSTRAINT IF EXISTS ck_pm_handover_request_mode;

ALTER TABLE project_manager_handover_request
    ADD CONSTRAINT ck_pm_handover_request_mode
    CHECK (handover_mode IN ('approval', 'admin_direct'));

COMMIT;
