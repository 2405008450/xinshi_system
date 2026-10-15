-- 项目须知：仅在明确授权的目标数据库执行，不复制标注内容。
BEGIN;
CREATE TABLE IF NOT EXISTS project_notice_section (
    id uuid PRIMARY KEY,
    module varchar(20) NOT NULL CHECK (module IN ('translation', 'interpretation', 'recruitment')),
    section_key varchar(80) NOT NULL UNIQUE,
    title varchar(100) NOT NULL,
    parent_id uuid,
    sort_order integer NOT NULL,
    has_content boolean NOT NULL DEFAULT true,
    is_active boolean NOT NULL DEFAULT true,
    content_json jsonb,
    search_text text NOT NULL DEFAULT '',
    updated_by uuid REFERENCES app_user(id) ON DELETE SET NULL,
    updated_at timestamptz,
    structure_updated_at timestamptz,
    UNIQUE (module, id),
    FOREIGN KEY (module, parent_id) REFERENCES project_notice_section(module, id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_project_notice_module_parent_order
    ON project_notice_section(module, parent_id, sort_order);
CREATE TABLE IF NOT EXISTS project_notice_attachment (
    id uuid PRIMARY KEY,
    section_id uuid NOT NULL REFERENCES project_notice_section(id),
    original_name varchar(255) NOT NULL,
    storage_name varchar(80) NOT NULL UNIQUE,
    content_type varchar(255) NOT NULL,
    file_size integer NOT NULL CHECK (file_size > 0 AND file_size <= 20971520),
    uploaded_by uuid REFERENCES app_user(id) ON DELETE SET NULL,
    uploaded_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_project_notice_attachment_section_id
    ON project_notice_attachment(section_id);
COMMIT;
