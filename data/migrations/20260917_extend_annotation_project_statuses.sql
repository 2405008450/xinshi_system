-- 标注项目增加“暂停”和“主动放弃”状态，并同步扩展状态履历约束。

ALTER TABLE annotation_project
    DROP CONSTRAINT IF EXISTS ck_annotation_project_status;

ALTER TABLE annotation_project
    ADD CONSTRAINT ck_annotation_project_status CHECK (
        project_status IN (
            'initial_consultation','consultation_no_result','resource_sourcing',
            'resource_sourcing_cancelled','trial_preparation','trial_in_progress',
            'trial_passed','trial_failed','trial_partially_passed','project_in_progress',
            'sent_to_client','client_feedback','cancelled','partially_cancelled',
            'paused','actively_abandoned'
        )
    );

ALTER TABLE annotation_project_status_history
    DROP CONSTRAINT IF EXISTS ck_annotation_status_history_from,
    DROP CONSTRAINT IF EXISTS ck_annotation_status_history_to;

ALTER TABLE annotation_project_status_history
    ADD CONSTRAINT ck_annotation_status_history_from CHECK (
        from_status IS NULL OR from_status IN (
            'initial_consultation','consultation_no_result','resource_sourcing',
            'resource_sourcing_cancelled','trial_preparation','trial_in_progress',
            'trial_passed','trial_failed','trial_partially_passed','project_in_progress',
            'sent_to_client','client_feedback','cancelled','partially_cancelled',
            'paused','actively_abandoned'
        )
    ),
    ADD CONSTRAINT ck_annotation_status_history_to CHECK (
        to_status IN (
            'initial_consultation','consultation_no_result','resource_sourcing',
            'resource_sourcing_cancelled','trial_preparation','trial_in_progress',
            'trial_passed','trial_failed','trial_partially_passed','project_in_progress',
            'sent_to_client','client_feedback','cancelled','partially_cancelled',
            'paused','actively_abandoned'
        )
    );
