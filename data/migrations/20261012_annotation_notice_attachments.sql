-- 标注须知附件；仅在明确授权的目标数据库执行。
BEGIN;
CREATE TABLE IF NOT EXISTS annotation_notice_attachment (
    id uuid PRIMARY KEY,
    section_id uuid NOT NULL REFERENCES annotation_notice_section(id),
    original_name varchar(255) NOT NULL,
    storage_name varchar(80) NOT NULL UNIQUE,
    content_type varchar(255) NOT NULL,
    file_size integer NOT NULL CHECK (file_size > 0 AND file_size <= 20971520),
    uploaded_by uuid REFERENCES app_user(id) ON DELETE SET NULL,
    uploaded_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_annotation_notice_attachment_section_id
    ON annotation_notice_attachment(section_id);
COMMIT;
