BEGIN;

ALTER TABLE annotation_custom_field_definition
    DROP CONSTRAINT IF EXISTS ck_annotation_custom_field_type;
ALTER TABLE annotation_custom_field_definition
    ADD CONSTRAINT ck_annotation_custom_field_type CHECK (
        data_type IN ('text','number','date','datetime','boolean','single_select','multi_select','url')
        OR (data_type = 'image' AND table_code = 'account_assignment')
    );

CREATE TABLE IF NOT EXISTS annotation_custom_field_image (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    field_definition_id UUID NOT NULL REFERENCES annotation_custom_field_definition(id) ON DELETE CASCADE,
    uploaded_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    original_name VARCHAR(255) NOT NULL,
    storage_name VARCHAR(255) NOT NULL UNIQUE,
    content_type VARCHAR(100) NOT NULL,
    file_size BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_annotation_custom_image_project_field
    ON annotation_custom_field_image(project_id, field_definition_id);
CREATE INDEX IF NOT EXISTS ix_annotation_custom_image_created_at
    ON annotation_custom_field_image(created_at);

CREATE TABLE IF NOT EXISTS annotation_account_assignment_image (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL REFERENCES annotation_account_assignment(id) ON DELETE CASCADE,
    field_definition_id UUID NOT NULL REFERENCES annotation_custom_field_definition(id) ON DELETE CASCADE,
    image_id UUID NOT NULL REFERENCES annotation_custom_field_image(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_annotation_assignment_image_field UNIQUE (assignment_id, field_definition_id)
);
CREATE INDEX IF NOT EXISTS ix_annotation_assignment_image_image
    ON annotation_account_assignment_image(image_id);

COMMIT;
