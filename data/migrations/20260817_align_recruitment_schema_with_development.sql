-- 对齐开发库与云端招聘表结构。
-- 仅补齐兼容字段、索引和约束，不复制或覆盖业务数据。

BEGIN;

ALTER TABLE recruitment_project
    ADD COLUMN IF NOT EXISTS position_name_type VARCHAR(500),
    ADD COLUMN IF NOT EXISTS recruitment_headcount INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS foreign_language_direction VARCHAR(500),
    ADD COLUMN IF NOT EXISTS proposed_start_date DATE,
    ADD COLUMN IF NOT EXISTS employment_period VARCHAR(500),
    ADD COLUMN IF NOT EXISTS service_fee VARCHAR(500);

-- 当前代码和前端统一使用 pending_setup，修正旧开发库遗留默认值。
ALTER TABLE recruitment_project
    ALTER COLUMN project_status SET DEFAULT 'pending_setup';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'recruitment_project'::regclass
          AND conname = 'ck_recruitment_headcount_nonnegative'
    ) THEN
        ALTER TABLE recruitment_project
            ADD CONSTRAINT ck_recruitment_headcount_nonnegative
            CHECK (recruitment_headcount >= 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'recruitment_project'::regclass
          AND conname = 'ck_recruitment_headcount_min'
    ) THEN
        ALTER TABLE recruitment_project
            ADD CONSTRAINT ck_recruitment_headcount_min
            CHECK (headcount_min IS NULL OR headcount_min >= 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'recruitment_project'::regclass
          AND conname = 'ck_recruitment_headcount_range'
    ) THEN
        ALTER TABLE recruitment_project
            ADD CONSTRAINT ck_recruitment_headcount_range
            CHECK (headcount_max IS NULL OR headcount_max >= headcount_min);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'recruitment_project'::regclass
          AND conname = 'ck_recruitment_employment_range'
    ) THEN
        ALTER TABLE recruitment_project
            ADD CONSTRAINT ck_recruitment_employment_range
            CHECK (
                employment_end IS NULL OR employment_start IS NULL
                OR employment_end >= employment_start
            );
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'recruitment_project'::regclass
          AND conname = 'ck_recruitment_service_fee_rate'
    ) THEN
        ALTER TABLE recruitment_project
            ADD CONSTRAINT ck_recruitment_service_fee_rate
            CHECK (service_fee_rate IS NULL OR (service_fee_rate >= 0 AND service_fee_rate <= 100));
    END IF;
END
$$;

ALTER TABLE recruitment_candidate
    ADD COLUMN IF NOT EXISTS sequence_no INTEGER,
    ADD COLUMN IF NOT EXISTS entry_date DATE,
    ADD COLUMN IF NOT EXISTS resume_source VARCHAR(100);

CREATE INDEX IF NOT EXISTS ix_recruitment_candidate_name
    ON recruitment_candidate(candidate_name);
CREATE INDEX IF NOT EXISTS ix_recruitment_candidate_stage
    ON recruitment_candidate(stage);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'recruitment_candidate'::regclass
          AND conname = 'uq_recruitment_candidate_sequence'
    ) THEN
        ALTER TABLE recruitment_candidate
            ADD CONSTRAINT uq_recruitment_candidate_sequence
            UNIQUE (project_id, sequence_no);
    END IF;
END
$$;

-- 当前接口要求沟通日期和内容必填；开发库旧表曾允许空值。
ALTER TABLE recruitment_candidate_communication
    ALTER COLUMN communication_date SET NOT NULL,
    ALTER COLUMN details SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'interpretation_project'::regclass
          AND conname = 'ck_interpretation_required_interpreter_count'
    ) THEN
        ALTER TABLE interpretation_project
            ADD CONSTRAINT ck_interpretation_required_interpreter_count
            CHECK (required_interpreter_count IS NULL OR required_interpreter_count >= 0);
    END IF;
END
$$;

COMMIT;
