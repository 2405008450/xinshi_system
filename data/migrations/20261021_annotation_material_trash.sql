-- 显式执行；历史资料保持有效，不自动清理回收站。
BEGIN;
ALTER TABLE annotation_material_file ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
ALTER TABLE annotation_material_file ADD COLUMN IF NOT EXISTS deleted_by uuid REFERENCES app_user(id) ON DELETE SET NULL;
ALTER TABLE annotation_material_file ADD COLUMN IF NOT EXISTS deleted_by_name varchar(255);
ALTER TABLE annotation_material_file ADD COLUMN IF NOT EXISTS deleted_folder_path varchar(500);
ALTER TABLE annotation_material_file ADD COLUMN IF NOT EXISTS trash_token uuid;
CREATE INDEX IF NOT EXISTS ix_annotation_material_file_deleted_at ON annotation_material_file(deleted_at);
COMMIT;
