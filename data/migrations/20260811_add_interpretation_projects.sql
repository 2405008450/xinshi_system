BEGIN;

CREATE TABLE IF NOT EXISTS interpretation_language (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label VARCHAR(100) NOT NULL,
    is_custom BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_interpretation_language_label UNIQUE (label)
);

CREATE TABLE IF NOT EXISTS interpretation_project (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_no VARCHAR(50) NOT NULL UNIQUE,
    project_name VARCHAR(500),
    project_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    task_description TEXT,
    consultation_id UUID REFERENCES consultation(id) ON DELETE SET NULL,
    client_id UUID REFERENCES client(id) ON DELETE RESTRICT,
    sub_client_id UUID REFERENCES sub_client(id) ON DELETE SET NULL,
    contact_name VARCHAR(255),
    customer_order_no VARCHAR(150),
    project_status VARCHAR(50) NOT NULL DEFAULT 'initial_follow_up',
    locations JSONB NOT NULL DEFAULT '[]'::jsonb,
    customer_budget VARCHAR(500),
    customer_consultation_time TIMESTAMP,
    customer_confirmation_time TIMESTAMP,
    interpretation_domain TEXT,
    interpretation_content TEXT,
    file_path TEXT,
    quotation_path TEXT,
    contract_path TEXT,
    client_rating VARCHAR(50),
    client_rating_note TEXT,
    remarks TEXT,
    email_subject_preview TEXT,
    social_post_request TEXT,
    resource_request TEXT,
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_interpretation_project_consultation UNIQUE (consultation_id)
);

CREATE INDEX IF NOT EXISTS ix_interpretation_project_status ON interpretation_project(project_status);
CREATE INDEX IF NOT EXISTS ix_interpretation_project_client ON interpretation_project(client_id);
CREATE INDEX IF NOT EXISTS ix_interpretation_project_created_at ON interpretation_project(created_at);

CREATE TABLE IF NOT EXISTS interpretation_project_time_range (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES interpretation_project(id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    scheduled_start TIMESTAMP NOT NULL,
    scheduled_end TIMESTAMP NOT NULL,
    actual_start TIMESTAMP,
    actual_end TIMESTAMP,
    CONSTRAINT uq_interpretation_time_range_sequence UNIQUE (project_id, sequence_no),
    CONSTRAINT ck_interpretation_scheduled_range CHECK (scheduled_end >= scheduled_start),
    CONSTRAINT ck_interpretation_actual_range CHECK (
        actual_end IS NULL OR (actual_start IS NOT NULL AND actual_end >= actual_start)
    )
);
CREATE INDEX IF NOT EXISTS ix_interpretation_time_range_scheduled
    ON interpretation_project_time_range(scheduled_start, scheduled_end);

CREATE TABLE IF NOT EXISTS interpretation_project_language_direction (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES interpretation_project(id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    source_language_id UUID NOT NULL REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    target_language_id UUID NOT NULL REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    CONSTRAINT uq_interpretation_direction_sequence UNIQUE (project_id, sequence_no),
    CONSTRAINT ck_interpretation_direction_distinct CHECK (source_language_id <> target_language_id)
);

CREATE TABLE IF NOT EXISTS interpretation_project_interpreter (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES interpretation_project(id) ON DELETE CASCADE,
    translator_id UUID NOT NULL REFERENCES translator(id) ON DELETE RESTRICT,
    sequence_no INTEGER NOT NULL,
    customer_rating VARCHAR(50),
    evaluation_note TEXT,
    CONSTRAINT uq_interpretation_project_translator UNIQUE (project_id, translator_id),
    CONSTRAINT uq_interpretation_interpreter_sequence UNIQUE (project_id, sequence_no)
);

COMMIT;
