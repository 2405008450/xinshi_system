-- 公司管理独立栏目和附件表；可重复执行，不覆盖用户设置。
BEGIN;
CREATE TABLE IF NOT EXISTS company_management_section (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_key VARCHAR(80) NOT NULL UNIQUE,
    title VARCHAR(100) NOT NULL,
    parent_id UUID REFERENCES company_management_section(id) ON DELETE RESTRICT,
    sort_order INTEGER NOT NULL,
    has_content BOOLEAN NOT NULL DEFAULT true,
    is_active BOOLEAN NOT NULL DEFAULT true,
    content_json JSONB,
    search_text TEXT NOT NULL DEFAULT '',
    updated_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    updated_at TIMESTAMP,
    structure_updated_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_company_management_section_parent_order
    ON company_management_section(parent_id, sort_order);
CREATE TABLE IF NOT EXISTS company_management_attachment (
    id UUID PRIMARY KEY,
    section_id UUID NOT NULL REFERENCES company_management_section(id),
    original_name VARCHAR(255) NOT NULL,
    storage_name VARCHAR(80) NOT NULL UNIQUE,
    content_type VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    uploaded_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    uploaded_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_company_management_attachment_section_id
    ON company_management_attachment(section_id);
INSERT INTO company_management_section (section_key, title, sort_order, structure_updated_at)
VALUES ('company_rules', '公司制度', 1, LOCALTIMESTAMP),
       ('human_resources', '人事行政', 2, LOCALTIMESTAMP),
       ('finance_rules', '财务规范', 3, LOCALTIMESTAMP),
       ('templates', '常用模板', 4, LOCALTIMESTAMP)
ON CONFLICT (section_key) DO NOTHING;
COMMIT;