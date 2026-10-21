-- Office 功能默认关闭；仅在已备份并明确选定的目标数据库显式执行。
BEGIN;
CREATE TABLE IF NOT EXISTS annotation_office_session (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES annotation_project(id) ON DELETE CASCADE,
    file_id UUID REFERENCES annotation_material_file(id) ON DELETE CASCADE,
    base_version_id UUID,
    owner_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    owner_name VARCHAR(255) NOT NULL,
    mode VARCHAR(10) NOT NULL,
    state VARCHAR(20) NOT NULL,
    document_key VARCHAR(64) NOT NULL UNIQUE,
    original_name VARCHAR(255) NOT NULL,
    folder_id UUID,
    source_upload_id UUID,
    staged_upload_id UUID,
    staged_revision INTEGER,
    created_at TIMESTAMPTZ NOT NULL,
    lease_until TIMESTAMPTZ NOT NULL,
    active_save_id UUID,
    saved_version_id UUID
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_annotation_office_writer ON annotation_office_session(file_id)
    WHERE mode = 'edit' AND state IN ('open','saving');
CREATE INDEX IF NOT EXISTS ix_annotation_office_session_project_id ON annotation_office_session(project_id);
CREATE TABLE IF NOT EXISTS annotation_office_save (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES annotation_office_session(id) ON DELETE CASCADE,
    state VARCHAR(20) NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    error VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    version_id UUID
);
CREATE INDEX IF NOT EXISTS ix_annotation_office_save_session_id ON annotation_office_save(session_id);
COMMIT;
