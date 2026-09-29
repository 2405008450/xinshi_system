BEGIN;
CREATE TABLE IF NOT EXISTS annotation_material_upload (
    id UUID PRIMARY KEY,
    uploaded_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    uploader_name VARCHAR(255) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    storage_key VARCHAR(64) NOT NULL UNIQUE,
    file_size INTEGER NOT NULL,
    content_type VARCHAR(255) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    consumed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_annotation_material_upload_expires_at ON annotation_material_upload(expires_at);
CREATE TABLE IF NOT EXISTS annotation_material_file (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    category VARCHAR(20) NOT NULL CONSTRAINT ck_annotation_material_category CHECK (category IN ('project','quotation','contract')),
    created_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_annotation_material_file_project_id ON annotation_material_file(project_id);
CREATE TABLE IF NOT EXISTS annotation_material_version (
    id UUID PRIMARY KEY,
    file_id UUID NOT NULL REFERENCES annotation_material_file(id) ON DELETE CASCADE,
    upload_id UUID NOT NULL UNIQUE REFERENCES annotation_material_upload(id),
    version_no INTEGER NOT NULL,
    UNIQUE(file_id, version_no)
);
CREATE INDEX IF NOT EXISTS ix_annotation_material_version_file_id ON annotation_material_version(file_id);
CREATE TABLE IF NOT EXISTS annotation_material_deletion (
    storage_key VARCHAR(64) PRIMARY KEY,
    attempts INTEGER NOT NULL,
    last_error VARCHAR(500),
    created_at TIMESTAMP NOT NULL
);
COMMIT;
