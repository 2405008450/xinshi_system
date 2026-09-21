-- 标注项目“试标/试采管理”工作台：语言方向、候选阶段、报价、三段时间、项目评价与跟进日志。

ALTER TABLE annotation_trial_record
    ADD COLUMN IF NOT EXISTS language_item_id UUID,
    ADD COLUMN IF NOT EXISTS activity_type VARCHAR(30) NOT NULL DEFAULT 'trial',
    ADD COLUMN IF NOT EXISTS duty_role VARCHAR(30) NOT NULL DEFAULT 'executor',
    ADD COLUMN IF NOT EXISTS candidate_stage VARCHAR(30) NOT NULL DEFAULT 'backup',
    ADD COLUMN IF NOT EXISTS willingness_level VARCHAR(20),
    ADD COLUMN IF NOT EXISTS quote_amount NUMERIC(18, 6),
    ADD COLUMN IF NOT EXISTS quote_currency VARCHAR(3),
    ADD COLUMN IF NOT EXISTS billing_unit VARCHAR(30),
    ADD COLUMN IF NOT EXISTS started_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS cooperation_level VARCHAR(20),
    ADD COLUMN IF NOT EXISTS cooperation_note TEXT,
    ADD COLUMN IF NOT EXISTS punctuality_level VARCHAR(20),
    ADD COLUMN IF NOT EXISTS punctuality_note TEXT,
    ADD COLUMN IF NOT EXISTS overall_score INTEGER,
    ADD COLUMN IF NOT EXISTS manager_comment TEXT;

UPDATE annotation_trial_record
SET candidate_stage = CASE trial_status
    WHEN 'in_progress' THEN 'in_progress'
    WHEN 'submitted' THEN 'submitted'
    WHEN 'reviewing' THEN 'submitted'
    WHEN 'completed' THEN 'reviewed'
    WHEN 'cancelled' THEN 'withdrawn'
    ELSE 'backup'
END
WHERE candidate_stage = 'backup';

ALTER TABLE annotation_trial_record
    DROP CONSTRAINT IF EXISTS uq_annotation_trial_person_round,
    DROP CONSTRAINT IF EXISTS ck_annotation_trial_activity_type,
    DROP CONSTRAINT IF EXISTS ck_annotation_trial_duty_role,
    DROP CONSTRAINT IF EXISTS ck_annotation_trial_candidate_stage,
    DROP CONSTRAINT IF EXISTS ck_annotation_trial_willingness,
    DROP CONSTRAINT IF EXISTS ck_annotation_trial_quote_amount,
    DROP CONSTRAINT IF EXISTS ck_annotation_trial_billing_unit,
    DROP CONSTRAINT IF EXISTS ck_annotation_trial_cooperation,
    DROP CONSTRAINT IF EXISTS ck_annotation_trial_punctuality,
    DROP CONSTRAINT IF EXISTS ck_annotation_trial_overall_score,
    DROP CONSTRAINT IF EXISTS ck_annotation_trial_time_range;

ALTER TABLE annotation_trial_record
    ADD CONSTRAINT ck_annotation_trial_activity_type CHECK (activity_type IN ('trial','collection')),
    ADD CONSTRAINT ck_annotation_trial_duty_role CHECK (duty_role IN ('executor','quality_inspector')),
    ADD CONSTRAINT ck_annotation_trial_candidate_stage CHECK (
        candidate_stage IN ('backup','contacted','pending_confirmation','confirmed','in_progress','submitted','reviewed','withdrawn')
    ),
    ADD CONSTRAINT ck_annotation_trial_willingness CHECK (
        willingness_level IS NULL OR willingness_level IN ('high','medium','low')
    ),
    ADD CONSTRAINT ck_annotation_trial_quote_amount CHECK (quote_amount IS NULL OR quote_amount > 0),
    ADD CONSTRAINT ck_annotation_trial_billing_unit CHECK (
        billing_unit IS NULL OR billing_unit IN ('occurrence','item','work_hour','effective_hour')
    ),
    ADD CONSTRAINT ck_annotation_trial_cooperation CHECK (
        cooperation_level IS NULL OR cooperation_level IN ('high','medium','low')
    ),
    ADD CONSTRAINT ck_annotation_trial_punctuality CHECK (
        punctuality_level IS NULL OR punctuality_level IN ('high','medium','low')
    ),
    ADD CONSTRAINT ck_annotation_trial_overall_score CHECK (
        overall_score IS NULL OR overall_score BETWEEN 1 AND 10
    ),
    ADD CONSTRAINT ck_annotation_trial_time_range CHECK (
        deadline_at IS NULL OR started_at IS NULL OR deadline_at >= started_at
    );

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_annotation_trial_language_item'
    ) THEN
        ALTER TABLE annotation_trial_record
        ADD CONSTRAINT fk_annotation_trial_language_item
        FOREIGN KEY (language_item_id) REFERENCES annotation_project_language_item(id) ON DELETE SET NULL;
    END IF;
END $$;

DROP INDEX IF EXISTS uq_annotation_trial_business_identity;
CREATE UNIQUE INDEX uq_annotation_trial_business_identity
    ON annotation_trial_record (
        project_id, person_id, language_item_id, activity_type, duty_role, round_no
    ) NULLS NOT DISTINCT;
CREATE INDEX IF NOT EXISTS ix_annotation_trial_project_stage
    ON annotation_trial_record(project_id, candidate_stage);
CREATE INDEX IF NOT EXISTS ix_annotation_trial_language_item
    ON annotation_trial_record(language_item_id);

CREATE TABLE IF NOT EXISTS annotation_trial_strategy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    language_item_id UUID NOT NULL REFERENCES annotation_project_language_item(id) ON DELETE CASCADE,
    planned_headcount INTEGER NOT NULL DEFAULT 1 CHECK (planned_headcount > 0),
    conversion_rate NUMERIC(5, 4) NOT NULL DEFAULT 0.1000 CHECK (conversion_rate > 0 AND conversion_rate <= 1),
    strategy_note TEXT,
    updated_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_annotation_trial_strategy_language UNIQUE(project_id, language_item_id)
);
CREATE INDEX IF NOT EXISTS ix_annotation_trial_strategy_project
    ON annotation_trial_strategy(project_id);

CREATE TABLE IF NOT EXISTS annotation_trial_follow_up (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trial_id UUID NOT NULL REFERENCES annotation_trial_record(id) ON DELETE CASCADE,
    follow_up_type VARCHAR(30) NOT NULL DEFAULT 'other'
        CHECK (follow_up_type IN ('contact','status','schedule','quote','result','other')),
    content TEXT NOT NULL,
    next_follow_up_at TIMESTAMP,
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_annotation_trial_follow_up_timeline
    ON annotation_trial_follow_up(trial_id, created_at DESC);
