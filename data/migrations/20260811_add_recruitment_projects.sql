BEGIN;

CREATE TABLE IF NOT EXISTS recruitment_project (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_no VARCHAR(50) NOT NULL,
    project_name VARCHAR(500),
    job_description TEXT,
    position_title VARCHAR(255),
    headcount_min INTEGER,
    headcount_max INTEGER,
    project_status VARCHAR(50) NOT NULL DEFAULT 'pending_setup',
    consultation_id UUID REFERENCES consultation(id) ON DELETE SET NULL,
    client_id UUID REFERENCES client(id) ON DELETE RESTRICT,
    sub_client_id UUID REFERENCES sub_client(id) ON DELETE SET NULL,
    contact_name VARCHAR(255),
    customer_order_no VARCHAR(150),
    client_manager_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    client_manager_name_snapshot VARCHAR(255),
    target_onboard_type VARCHAR(20) NOT NULL DEFAULT 'date',
    target_onboard_date DATE,
    employment_start DATE,
    employment_end DATE,
    work_location VARCHAR(500),
    service_fee_type VARCHAR(30),
    service_fee_currency VARCHAR(10) DEFAULT 'CNY',
    service_fee_amount NUMERIC(14, 2),
    service_fee_rate NUMERIC(7, 4),
    service_fee_note TEXT,
    customer_consultation_time TIMESTAMP,
    customer_confirmation_time TIMESTAMP,
    project_path TEXT,
    quotation_path TEXT,
    contract_path TEXT,
    remarks TEXT,
    email_subject_preview TEXT,
    social_post_request TEXT,
    resource_request TEXT,
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_recruitment_project_order_no UNIQUE (order_no),
    CONSTRAINT uq_recruitment_project_consultation UNIQUE (consultation_id),
    CONSTRAINT ck_recruitment_headcount_min CHECK (headcount_min IS NULL OR headcount_min >= 0),
    CONSTRAINT ck_recruitment_headcount_range CHECK (headcount_max IS NULL OR headcount_max >= headcount_min),
    CONSTRAINT ck_recruitment_employment_range CHECK (employment_end IS NULL OR employment_start IS NULL OR employment_end >= employment_start),
    CONSTRAINT ck_recruitment_service_fee_rate CHECK (service_fee_rate IS NULL OR (service_fee_rate >= 0 AND service_fee_rate <= 100))
);
CREATE INDEX IF NOT EXISTS ix_recruitment_project_status ON recruitment_project(project_status);
CREATE INDEX IF NOT EXISTS ix_recruitment_project_client ON recruitment_project(client_id);
CREATE INDEX IF NOT EXISTS ix_recruitment_project_created_at ON recruitment_project(created_at);

CREATE TABLE IF NOT EXISTS recruitment_project_language_direction (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES recruitment_project(id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    direction_type VARCHAR(20) NOT NULL,
    source_language_id UUID NOT NULL REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    target_language_id UUID REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    CONSTRAINT uq_recruitment_direction_sequence UNIQUE (project_id, sequence_no),
    CONSTRAINT ck_recruitment_direction_type CHECK (direction_type IN ('single', 'translation')),
    CONSTRAINT ck_recruitment_direction_target_required CHECK (direction_type = 'single' OR target_language_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS recruitment_project_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES recruitment_project(id) ON DELETE CASCADE,
    from_status VARCHAR(50),
    to_status VARCHAR(50),
    note TEXT,
    is_system BOOLEAN NOT NULL DEFAULT TRUE,
    operator_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_recruitment_progress_project_time
    ON recruitment_project_progress(project_id, occurred_at);

CREATE TABLE IF NOT EXISTS recruitment_candidate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES recruitment_project(id) ON DELETE CASCADE,
    candidate_name VARCHAR(255) NOT NULL,
    contact_info VARCHAR(500),
    resume_path TEXT,
    stage VARCHAR(50) NOT NULL DEFAULT 'screening',
    recommended_at TIMESTAMP,
    interview_at TIMESTAMP,
    offer_at TIMESTAMP,
    planned_onboard_date DATE,
    actual_onboard_date DATE,
    owner_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    next_follow_up_at TIMESTAMP,
    remarks TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_recruitment_candidate_project ON recruitment_candidate(project_id);
CREATE INDEX IF NOT EXISTS ix_recruitment_candidate_stage ON recruitment_candidate(stage);

-- 兼容早期招聘模拟模块已经创建、但字段结构不同的空表或试用表。
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS position_title VARCHAR(255);
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS headcount_min INTEGER;
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS headcount_max INTEGER;
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS client_manager_id UUID REFERENCES app_user(id) ON DELETE SET NULL;
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS client_manager_name_snapshot VARCHAR(255);
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS target_onboard_type VARCHAR(20) NOT NULL DEFAULT 'date';
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS target_onboard_date DATE;
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS employment_start DATE;
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS employment_end DATE;
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS service_fee_type VARCHAR(30);
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS service_fee_currency VARCHAR(10) DEFAULT 'CNY';
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS service_fee_amount NUMERIC(14, 2);
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS service_fee_rate NUMERIC(7, 4);
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS service_fee_note TEXT;
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS project_path TEXT;

ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS contact_info VARCHAR(500);
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS stage VARCHAR(50) NOT NULL DEFAULT 'screening';
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS recommended_at TIMESTAMP;
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS interview_at TIMESTAMP;
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS offer_at TIMESTAMP;
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS planned_onboard_date DATE;
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS actual_onboard_date DATE;
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES app_user(id) ON DELETE SET NULL;
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS next_follow_up_at TIMESTAMP;
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS remarks TEXT;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='recruitment_project' AND column_name='position_name_type') THEN
        EXECUTE 'UPDATE recruitment_project SET position_title = COALESCE(position_title, position_name_type)';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='recruitment_project' AND column_name='recruitment_headcount') THEN
        EXECUTE 'UPDATE recruitment_project SET headcount_min = COALESCE(headcount_min, recruitment_headcount), headcount_max = COALESCE(headcount_max, recruitment_headcount)';
        EXECUTE 'ALTER TABLE recruitment_project ALTER COLUMN recruitment_headcount SET DEFAULT 0';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='recruitment_project' AND column_name='proposed_start_date') THEN
        EXECUTE 'UPDATE recruitment_project SET target_onboard_date = COALESCE(target_onboard_date, proposed_start_date)';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='recruitment_project' AND column_name='service_fee') THEN
        EXECUTE 'UPDATE recruitment_project SET service_fee_note = COALESCE(service_fee_note, service_fee)';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='recruitment_candidate' AND column_name='sequence_no') THEN
        EXECUTE 'ALTER TABLE recruitment_candidate ALTER COLUMN sequence_no DROP NOT NULL';
    END IF;
END
$$;

COMMIT;
