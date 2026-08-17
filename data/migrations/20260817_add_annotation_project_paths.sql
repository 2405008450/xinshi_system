BEGIN;

ALTER TABLE annotation_project
    ADD COLUMN IF NOT EXISTS project_path TEXT,
    ADD COLUMN IF NOT EXISTS quotation_path TEXT,
    ADD COLUMN IF NOT EXISTS contract_path TEXT;

COMMENT ON COLUMN annotation_project.project_path IS '标注项目文件路径';
COMMENT ON COLUMN annotation_project.quotation_path IS '标注项目报价单路径';
COMMENT ON COLUMN annotation_project.contract_path IS '标注项目合同路径';

COMMIT;
