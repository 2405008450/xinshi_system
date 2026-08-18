BEGIN;

ALTER TABLE translation_project
    ADD COLUMN IF NOT EXISTS annotation_project_id UUID,
    ADD COLUMN IF NOT EXISTS annotation_migrated_at TIMESTAMP;

-- 共享语种目录沿用既有口译语种表，确保本迁移可独立执行。
CREATE TABLE IF NOT EXISTS interpretation_language (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label VARCHAR(100) NOT NULL,
    is_custom BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_interpretation_language_label UNIQUE (label)
);

CREATE TABLE IF NOT EXISTS annotation_project (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_no VARCHAR(50) NOT NULL,
    project_name VARCHAR(500),
    project_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    task_description TEXT,
    consultation_id UUID REFERENCES consultation(id) ON DELETE SET NULL,
    client_id UUID REFERENCES client(id) ON DELETE RESTRICT,
    sub_client_id UUID REFERENCES sub_client(id) ON DELETE SET NULL,
    contact_name VARCHAR(255),
    customer_order_no VARCHAR(150),
    project_status VARCHAR(50) NOT NULL DEFAULT 'pending_confirmation',
    potential_demand TEXT,
    task_dispatched_at TIMESTAMP,
    task_submitted_at TIMESTAMP,
    client_manager_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    customer_consultation_time TIMESTAMP,
    customer_confirmation_time TIMESTAMP,
    legacy_translation_project_id UUID REFERENCES translation_project(id) ON DELETE SET NULL,
    legacy_order_no VARCHAR(50),
    legacy_status VARCHAR(50),
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_annotation_project_order_no UNIQUE (order_no),
    CONSTRAINT uq_annotation_project_consultation UNIQUE (consultation_id),
    CONSTRAINT uq_annotation_project_legacy_translation UNIQUE (legacy_translation_project_id),
    CONSTRAINT ck_annotation_project_task_times CHECK (
        task_submitted_at IS NULL OR task_dispatched_at IS NULL
        OR task_submitted_at >= task_dispatched_at
    )
);

CREATE INDEX IF NOT EXISTS ix_annotation_project_status
    ON annotation_project(project_status);
CREATE INDEX IF NOT EXISTS ix_annotation_project_client
    ON annotation_project(client_id);
CREATE INDEX IF NOT EXISTS ix_annotation_project_client_manager
    ON annotation_project(client_manager_id);
CREATE INDEX IF NOT EXISTS ix_annotation_project_created_at
    ON annotation_project(created_at);

CREATE TABLE IF NOT EXISTS annotation_project_language_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    source_language_id UUID NOT NULL REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    target_language_id UUID REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    CONSTRAINT uq_annotation_language_item_sequence UNIQUE (project_id, sequence_no),
    CONSTRAINT ck_annotation_language_item_distinct CHECK (
        target_language_id IS NULL OR source_language_id <> target_language_id
    )
);

CREATE TABLE IF NOT EXISTS annotation_project_price_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    project_type VARCHAR(50),
    source_language_id UUID REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    target_language_id UUID REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    amount NUMERIC(18, 6) NOT NULL,
    currency VARCHAR(3),
    unit VARCHAR(50) NOT NULL,
    remarks TEXT,
    CONSTRAINT uq_annotation_price_item_sequence UNIQUE (project_id, sequence_no),
    CONSTRAINT ck_annotation_price_item_amount CHECK (amount > 0),
    CONSTRAINT ck_annotation_price_item_language_scope CHECK (
        target_language_id IS NULL OR source_language_id IS NOT NULL
    )
);

COMMIT;
