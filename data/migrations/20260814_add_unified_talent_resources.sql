-- 统一人才资源库：仅包含可重复执行的结构迁移。
-- 数据回填由 resource_service.backfill_resource_people 在应用启动时幂等执行。

CREATE TABLE IF NOT EXISTS resource_person (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_code VARCHAR(50) UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    cooperation_type VARCHAR(50),
    contact_info VARCHAR(500),
    primary_phone VARCHAR(50),
    secondary_phone VARCHAR(50),
    primary_email VARCHAR(255),
    secondary_email VARCHAR(255),
    other_contact VARCHAR(255),
    resume_path TEXT,
    gender VARCHAR(20),
    height VARCHAR(50),
    appearance VARCHAR(255),
    nationality VARCHAR(100),
    ethnicity VARCHAR(100),
    overall_rating TEXT,
    first_contact_date TIMESTAMP,
    remarks TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'standby'
        CHECK (status IN ('active', 'standby', 'inactive')),
    duplicate_review_required BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_resource_person_name ON resource_person(full_name);
CREATE INDEX IF NOT EXISTS ix_resource_person_primary_phone ON resource_person(primary_phone);
CREATE INDEX IF NOT EXISTS ix_resource_person_primary_email ON resource_person(primary_email);
CREATE INDEX IF NOT EXISTS ix_resource_person_status ON resource_person(status);

CREATE TABLE IF NOT EXISTS resource_capability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id UUID NOT NULL REFERENCES resource_person(id) ON DELETE CASCADE,
    capability_type VARCHAR(40) NOT NULL
        CHECK (capability_type IN ('written_translation', 'interpretation', 'annotation')),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'standby', 'inactive')),
    review_required BOOLEAN NOT NULL DEFAULT FALSE,
    source VARCHAR(30) NOT NULL DEFAULT 'manual',
    remarks TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_resource_person_capability UNIQUE (person_id, capability_type)
);
CREATE INDEX IF NOT EXISTS ix_resource_capability_type_status ON resource_capability(capability_type, status);

CREATE TABLE IF NOT EXISTS resource_written_translation_profile (
    person_id UUID PRIMARY KEY REFERENCES resource_person(id) ON DELETE CASCADE,
    languages VARCHAR(500), direction VARCHAR(50), domain_skills JSONB NOT NULL DEFAULT '[]'::jsonb,
    quality_score VARCHAR(50), default_priority INTEGER NOT NULL DEFAULT 0,
    daily_accept_count INTEGER, hourly_speed INTEGER, daily_word_capacity INTEGER,
    can_cloud_edit BOOLEAN, can_revision BOOLEAN, available_time_slot VARCHAR(100),
    schedule_remarks TEXT, availability_updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resource_interpretation_profile (
    person_id UUID PRIMARY KEY REFERENCES resource_person(id) ON DELETE CASCADE,
    languages VARCHAR(500), direction VARCHAR(50), interpretation_level VARCHAR(20),
    interpretation_modes JSONB NOT NULL DEFAULT '[]'::jsonb,
    domain_skills JSONB NOT NULL DEFAULT '[]'::jsonb,
    quality_score VARCHAR(50), evaluation_summary TEXT
);

CREATE TABLE IF NOT EXISTS resource_annotation_profile (
    person_id UUID PRIMARY KEY REFERENCES resource_person(id) ON DELETE CASCADE,
    task_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    data_modalities JSONB NOT NULL DEFAULT '[]'::jsonb,
    tools JSONB NOT NULL DEFAULT '[]'::jsonb,
    domain_skills JSONB NOT NULL DEFAULT '[]'::jsonb,
    quality_score VARCHAR(50), daily_capacity INTEGER, remarks TEXT
);

CREATE TABLE IF NOT EXISTS resource_career_profile (
    person_id UUID PRIMARY KEY REFERENCES resource_person(id) ON DELETE CASCADE,
    industries JSONB NOT NULL DEFAULT '[]'::jsonb,
    functions JSONB NOT NULL DEFAULT '[]'::jsonb,
    job_titles JSONB NOT NULL DEFAULT '[]'::jsonb,
    years_experience NUMERIC(5,2),
    preferred_locations JSONB NOT NULL DEFAULT '[]'::jsonb,
    expected_salary VARCHAR(255), summary TEXT
);

ALTER TABLE translator ADD COLUMN IF NOT EXISTS resource_person_id UUID;
CREATE UNIQUE INDEX IF NOT EXISTS uq_translator_resource_person
    ON translator(resource_person_id) WHERE resource_person_id IS NOT NULL;
ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS person_id UUID;
CREATE INDEX IF NOT EXISTS ix_recruitment_candidate_person ON recruitment_candidate(person_id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_translator_resource_person') THEN
        ALTER TABLE translator ADD CONSTRAINT fk_translator_resource_person
            FOREIGN KEY (resource_person_id) REFERENCES resource_person(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_recruitment_candidate_person') THEN
        ALTER TABLE recruitment_candidate ADD CONSTRAINT fk_recruitment_candidate_person
            FOREIGN KEY (person_id) REFERENCES resource_person(id) ON DELETE RESTRICT;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS annotation_project_assignee (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    person_id UUID NOT NULL REFERENCES resource_person(id) ON DELETE RESTRICT,
    sequence_no INTEGER NOT NULL,
    assignment_status VARCHAR(30) NOT NULL DEFAULT 'assigned',
    quality_score VARCHAR(50), evaluation_note TEXT,
    CONSTRAINT uq_annotation_project_assignee UNIQUE (project_id, person_id),
    CONSTRAINT uq_annotation_assignee_sequence UNIQUE (project_id, sequence_no)
);
CREATE INDEX IF NOT EXISTS ix_annotation_assignee_person ON annotation_project_assignee(person_id);
