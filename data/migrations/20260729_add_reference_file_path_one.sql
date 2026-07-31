ALTER TABLE translation_project
    ADD COLUMN IF NOT EXISTS reference_file_path_one VARCHAR(500);

COMMENT ON COLUMN translation_project.reference_file_path_one
    IS '老系统稿件安排字段：参考文件路径一';
