-- 口译项目状态时间线及各状态节点下的具体进度记录。
CREATE TABLE IF NOT EXISTS interpretation_project_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    from_status VARCHAR(50),
    to_status VARCHAR(50) NOT NULL,
    effective_on TIMESTAMP NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by UUID,
    change_note TEXT,
    CONSTRAINT fk_interpretation_status_history_project
        FOREIGN KEY (project_id) REFERENCES interpretation_project(id) ON DELETE CASCADE,
    CONSTRAINT fk_interpretation_status_history_user
        FOREIGN KEY (changed_by) REFERENCES app_user(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_interpretation_status_history_timeline
    ON interpretation_project_status_history(project_id, effective_on DESC, changed_at DESC);

CREATE INDEX IF NOT EXISTS ix_interpretation_status_history_status_date
    ON interpretation_project_status_history(to_status, effective_on);

INSERT INTO interpretation_project_status_history
    (project_id, from_status, to_status, effective_on, changed_by, changed_at)
SELECT p.id, NULL, p.project_status, p.created_at, p.created_by, p.created_at
FROM interpretation_project p
WHERE NOT EXISTS (
    SELECT 1 FROM interpretation_project_status_history h WHERE h.project_id = p.id
);
