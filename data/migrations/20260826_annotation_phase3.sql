BEGIN;

UPDATE annotation_project SET project_status = CASE project_status
    WHEN 'pending_confirmation' THEN 'initial_consultation'
    WHEN 'trial' THEN 'trial_in_progress'
    WHEN 'in_progress' THEN 'project_in_progress'
    ELSE project_status END
WHERE project_status IN ('pending_confirmation', 'trial', 'in_progress');

ALTER TABLE annotation_project
    ADD COLUMN IF NOT EXISTS language_region VARCHAR(255),
    ADD COLUMN IF NOT EXISTS status_effective_on DATE NOT NULL DEFAULT CURRENT_DATE,
    ADD COLUMN IF NOT EXISTS custom_values JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE annotation_project ALTER COLUMN project_status SET DEFAULT 'initial_consultation';
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_annotation_project_status') THEN
        ALTER TABLE annotation_project ADD CONSTRAINT ck_annotation_project_status CHECK (project_status IN (
            'initial_consultation','consultation_no_result','resource_sourcing','resource_sourcing_cancelled',
            'trial_preparation','trial_in_progress','trial_passed','trial_failed','trial_partially_passed',
            'project_in_progress','sent_to_client','client_feedback','cancelled','partially_cancelled'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS annotation_project_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    from_status VARCHAR(50), to_status VARCHAR(50) NOT NULL,
    effective_on DATE NOT NULL, changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by UUID REFERENCES app_user(id) ON DELETE SET NULL, change_note TEXT,
    CONSTRAINT ck_annotation_status_history_from CHECK (from_status IS NULL OR from_status IN ('initial_consultation','consultation_no_result','resource_sourcing','resource_sourcing_cancelled','trial_preparation','trial_in_progress','trial_passed','trial_failed','trial_partially_passed','project_in_progress','sent_to_client','client_feedback','cancelled','partially_cancelled')),
    CONSTRAINT ck_annotation_status_history_to CHECK (to_status IN ('initial_consultation','consultation_no_result','resource_sourcing','resource_sourcing_cancelled','trial_preparation','trial_in_progress','trial_passed','trial_failed','trial_partially_passed','project_in_progress','sent_to_client','client_feedback','cancelled','partially_cancelled'))
);
CREATE INDEX IF NOT EXISTS ix_annotation_status_history_timeline ON annotation_project_status_history(project_id, effective_on DESC, changed_at DESC);
CREATE INDEX IF NOT EXISTS ix_annotation_status_history_status_date ON annotation_project_status_history(to_status, effective_on);
INSERT INTO annotation_project_status_history(project_id, from_status, to_status, effective_on, changed_by, changed_at)
SELECT p.id, NULL, p.project_status, COALESCE(p.status_effective_on, p.created_at::date), p.created_by, p.created_at
FROM annotation_project p WHERE NOT EXISTS (SELECT 1 FROM annotation_project_status_history h WHERE h.project_id=p.id);

CREATE TABLE IF NOT EXISTS annotation_project_platform (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    platform_name VARCHAR(150), platform_url TEXT NOT NULL, sequence_no INTEGER NOT NULL CHECK(sequence_no>0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE, created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_annotation_platform_sequence UNIQUE(project_id, sequence_no)
);
CREATE INDEX IF NOT EXISTS ix_annotation_platform_project ON annotation_project_platform(project_id);

CREATE TABLE IF NOT EXISTS annotation_platform_member (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), platform_id UUID NOT NULL REFERENCES annotation_project_platform(id) ON DELETE CASCADE,
    person_id UUID REFERENCES resource_person(id) ON DELETE RESTRICT, nickname VARCHAR(255),
    registration_status VARCHAR(30) NOT NULL DEFAULT 'unregistered' CHECK(registration_status IN ('unregistered','registering','registered','registration_failed','disabled','not_required')),
    sequence_no INTEGER NOT NULL CHECK(sequence_no>0), custom_values JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_annotation_member_person UNIQUE(platform_id, person_id), CONSTRAINT uq_annotation_member_sequence UNIQUE(platform_id, sequence_no)
);
CREATE INDEX IF NOT EXISTS ix_annotation_member_person ON annotation_platform_member(person_id);
CREATE INDEX IF NOT EXISTS ix_annotation_member_registration_status ON annotation_platform_member(registration_status);
ALTER TABLE annotation_platform_member ALTER COLUMN person_id DROP NOT NULL;

CREATE TABLE IF NOT EXISTS annotation_platform_member_language (
    member_id UUID NOT NULL REFERENCES annotation_platform_member(id) ON DELETE CASCADE,
    language_item_id UUID NOT NULL REFERENCES annotation_project_language_item(id) ON DELETE RESTRICT,
    PRIMARY KEY(member_id, language_item_id)
);

CREATE TABLE IF NOT EXISTS annotation_platform_credential (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), member_id UUID NOT NULL REFERENCES annotation_platform_member(id) ON DELETE CASCADE,
    credential_kind VARCHAR(20) NOT NULL CHECK(credential_kind IN ('primary','backup')), sequence_no INTEGER NOT NULL CHECK(sequence_no>0),
    display_nickname VARCHAR(255), login_account_ciphertext BYTEA NOT NULL, login_account_fingerprint CHAR(64),
    password_ciphertext BYTEA NOT NULL, encryption_key_version VARCHAR(50) NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE,
    password_updated_at TIMESTAMP, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_annotation_credential_sequence UNIQUE(member_id, credential_kind, sequence_no)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_annotation_credential_active_primary ON annotation_platform_credential(member_id) WHERE credential_kind='primary' AND is_active;

CREATE TABLE IF NOT EXISTS annotation_trial_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    person_id UUID NOT NULL REFERENCES resource_person(id) ON DELETE RESTRICT,
    platform_member_id UUID REFERENCES annotation_platform_member(id) ON DELETE SET NULL,
    round_no INTEGER NOT NULL DEFAULT 1 CHECK(round_no>0), sequence_no INTEGER NOT NULL CHECK(sequence_no>0),
    willingness_text TEXT, trial_status VARCHAR(30) NOT NULL DEFAULT 'pending' CHECK(trial_status IN ('pending','in_progress','submitted','reviewing','completed','cancelled')),
    trial_result VARCHAR(30) CHECK(trial_result IS NULL OR trial_result IN ('passed','failed','partially_passed','withdrawn')),
    result_note TEXT, custom_values JSONB NOT NULL DEFAULT '{}'::jsonb, created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_annotation_trial_person_round UNIQUE(project_id, person_id, round_no),
    CONSTRAINT uq_annotation_trial_sequence UNIQUE(project_id, round_no, sequence_no)
);
CREATE INDEX IF NOT EXISTS ix_annotation_trial_project_status ON annotation_trial_record(project_id, trial_status);
CREATE INDEX IF NOT EXISTS ix_annotation_trial_person ON annotation_trial_record(person_id);

ALTER TABLE annotation_project_assignee
    ADD COLUMN IF NOT EXISTS assignment_role VARCHAR(30) NOT NULL DEFAULT 'annotator',
    ADD COLUMN IF NOT EXISTS language_item_id UUID,
    ADD COLUMN IF NOT EXISTS audio_duration_value NUMERIC(18,3),
    ADD COLUMN IF NOT EXISTS audio_duration_unit VARCHAR(20),
    ADD COLUMN IF NOT EXISTS custom_values JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE annotation_project_assignee DROP CONSTRAINT IF EXISTS uq_annotation_project_assignee;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_annotation_assignee_language_item') THEN
        ALTER TABLE annotation_project_assignee ADD CONSTRAINT fk_annotation_assignee_language_item FOREIGN KEY(language_item_id) REFERENCES annotation_project_language_item(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_annotation_assignee_role') THEN
        ALTER TABLE annotation_project_assignee ADD CONSTRAINT ck_annotation_assignee_role CHECK(assignment_role IN ('annotator','quality_inspector'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_annotation_assignee_audio_duration_value') THEN
        ALTER TABLE annotation_project_assignee ADD CONSTRAINT ck_annotation_assignee_audio_duration_value CHECK(audio_duration_value IS NULL OR audio_duration_value>=0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_annotation_assignee_audio_duration_unit') THEN
        ALTER TABLE annotation_project_assignee ADD CONSTRAINT ck_annotation_assignee_audio_duration_unit CHECK(audio_duration_unit IS NULL OR audio_duration_unit IN ('second','minute','hour'));
    END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS uq_annotation_project_assignee_scope ON annotation_project_assignee(project_id, person_id, language_item_id, assignment_role) NULLS NOT DISTINCT;

CREATE TABLE IF NOT EXISTS annotation_assignee_rate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), assignee_id UUID NOT NULL UNIQUE REFERENCES annotation_project_assignee(id) ON DELETE CASCADE,
    amount NUMERIC(18,6) NOT NULL CHECK(amount>0), currency VARCHAR(3), unit VARCHAR(30) NOT NULL CHECK(unit IN ('item','second','minute','hour')),
    remarks TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS annotation_custom_field_definition (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID REFERENCES annotation_project(id) ON DELETE CASCADE,
    table_code VARCHAR(30) NOT NULL CHECK(table_code IN ('project','account','trial','assignment')),
    field_key VARCHAR(100) NOT NULL, field_label VARCHAR(150) NOT NULL,
    data_type VARCHAR(30) NOT NULL CHECK(data_type IN ('text','number','date','datetime','boolean','single_select','multi_select','url')),
    options JSONB NOT NULL DEFAULT '[]'::jsonb, sequence_no INTEGER NOT NULL CHECK(sequence_no>0),
    is_required BOOLEAN NOT NULL DEFAULT FALSE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_annotation_custom_field_scope CHECK(
        (table_code='project' AND project_id IS NULL) OR
        (table_code IN ('account','trial','assignment') AND project_id IS NOT NULL)
    )
);
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_annotation_custom_field_scope') THEN
        ALTER TABLE annotation_custom_field_definition
            ADD CONSTRAINT ck_annotation_custom_field_scope CHECK(
                (table_code='project' AND project_id IS NULL) OR
                (table_code IN ('account','trial','assignment') AND project_id IS NOT NULL)
            );
    END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS uq_annotation_custom_field_scope_key ON annotation_custom_field_definition(project_id, table_code, field_key) NULLS NOT DISTINCT;
CREATE INDEX IF NOT EXISTS ix_annotation_custom_field_sequence ON annotation_custom_field_definition(project_id, table_code, sequence_no);

CREATE TABLE IF NOT EXISTS resource_request (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), request_no VARCHAR(50) NOT NULL UNIQUE,
    source_type VARCHAR(30) NOT NULL CHECK(source_type IN ('annotation','recruitment','interpretation','translation','other')),
    request_category VARCHAR(30) NOT NULL CHECK(request_category IN ('annotation_trial','annotation_formal','recruitment','interpretation','translation','other')),
    annotation_project_id UUID REFERENCES annotation_project(id) ON DELETE RESTRICT,
    recruitment_project_id UUID REFERENCES recruitment_project(id) ON DELETE RESTRICT,
    interpretation_project_id UUID REFERENCES interpretation_project(id) ON DELETE RESTRICT,
    translation_project_id UUID REFERENCES translation_project(id) ON DELETE RESTRICT, other_source_name VARCHAR(500),
    source_project_types_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb, source_order_no_snapshot VARCHAR(80),
    source_project_name_snapshot VARCHAR(500) NOT NULL, source_status_snapshot VARCHAR(50),
    client_id UUID REFERENCES client(id) ON DELETE RESTRICT, sub_client_id UUID REFERENCES sub_client(id) ON DELETE SET NULL,
    client_code_snapshot VARCHAR(60), client_short_name_snapshot VARCHAR(100), request_detail TEXT NOT NULL,
    progress_percent SMALLINT NOT NULL DEFAULT 0 CHECK(progress_percent BETWEEN 0 AND 100),
    priority VARCHAR(10) NOT NULL DEFAULT 'medium' CHECK(priority IN ('high','medium','low')),
    request_status VARCHAR(30) NOT NULL DEFAULT 'submitted' CHECK(request_status IN ('draft','submitted','in_progress','fulfilled','cancelled')),
    requested_by UUID REFERENCES app_user(id) ON DELETE SET NULL, requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    owner_id UUID REFERENCES app_user(id) ON DELETE SET NULL, completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_resource_request_completed_at CHECK(completed_at IS NULL OR completed_at>=requested_at),
    CONSTRAINT ck_resource_request_source_xor CHECK(
      (source_type='annotation' AND annotation_project_id IS NOT NULL AND recruitment_project_id IS NULL AND interpretation_project_id IS NULL AND translation_project_id IS NULL AND other_source_name IS NULL) OR
      (source_type='recruitment' AND annotation_project_id IS NULL AND recruitment_project_id IS NOT NULL AND interpretation_project_id IS NULL AND translation_project_id IS NULL AND other_source_name IS NULL) OR
      (source_type='interpretation' AND annotation_project_id IS NULL AND recruitment_project_id IS NULL AND interpretation_project_id IS NOT NULL AND translation_project_id IS NULL AND other_source_name IS NULL) OR
      (source_type='translation' AND annotation_project_id IS NULL AND recruitment_project_id IS NULL AND interpretation_project_id IS NULL AND translation_project_id IS NOT NULL AND other_source_name IS NULL) OR
      (source_type='other' AND annotation_project_id IS NULL AND recruitment_project_id IS NULL AND interpretation_project_id IS NULL AND translation_project_id IS NULL AND other_source_name IS NOT NULL)),
    CONSTRAINT ck_resource_request_category_source CHECK((source_type='annotation' AND request_category IN ('annotation_trial','annotation_formal')) OR source_type=request_category)
);
CREATE INDEX IF NOT EXISTS ix_resource_request_status_priority ON resource_request(request_status, priority, requested_at DESC);
CREATE INDEX IF NOT EXISTS ix_resource_request_source ON resource_request(source_type, requested_at DESC);
CREATE INDEX IF NOT EXISTS ix_resource_request_annotation ON resource_request(annotation_project_id) WHERE annotation_project_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_resource_request_recruitment ON resource_request(recruitment_project_id) WHERE recruitment_project_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_resource_request_interpretation ON resource_request(interpretation_project_id) WHERE interpretation_project_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_resource_request_translation ON resource_request(translation_project_id) WHERE translation_project_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_resource_request_client ON resource_request(client_id);
CREATE INDEX IF NOT EXISTS ix_resource_request_owner_status ON resource_request(owner_id, request_status);

CREATE TABLE IF NOT EXISTS resource_request_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), request_id UUID NOT NULL REFERENCES resource_request(id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL CHECK(sequence_no>0), source_language_id UUID REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    target_language_id UUID REFERENCES interpretation_language(id) ON DELETE RESTRICT, required_count INTEGER CHECK(required_count IS NULL OR required_count>0),
    requirement_detail TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_resource_request_item_sequence UNIQUE(request_id, sequence_no),
    CONSTRAINT ck_resource_request_item_languages CHECK(target_language_id IS NULL OR (source_language_id IS NOT NULL AND source_language_id<>target_language_id))
);
CREATE TABLE IF NOT EXISTS resource_request_progress_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), request_id UUID NOT NULL REFERENCES resource_request(id) ON DELETE CASCADE,
    progress_percent SMALLINT NOT NULL CHECK(progress_percent BETWEEN 0 AND 100), progress_note TEXT,
    changed_by UUID REFERENCES app_user(id) ON DELETE SET NULL, changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_resource_request_progress_timeline ON resource_request_progress_log(request_id, changed_at DESC);

CREATE OR REPLACE VIEW v_resource_request_display AS
SELECT r.*,
    COALESCE(ap.project_status, rp.project_status, ip.project_status, tp.project_status) AS current_project_status,
    COALESCE(ap.order_no, rp.order_no, ip.order_no, tp.order_no) AS current_order_no,
    COALESCE(ap.project_name, rp.project_name, ip.project_name, tp.project_name, r.other_source_name) AS current_project_name
FROM resource_request r
LEFT JOIN annotation_project ap ON ap.id=r.annotation_project_id
LEFT JOIN recruitment_project rp ON rp.id=r.recruitment_project_id
LEFT JOIN interpretation_project ip ON ip.id=r.interpretation_project_id
LEFT JOIN translation_project tp ON tp.id=r.translation_project_id;

COMMIT;
