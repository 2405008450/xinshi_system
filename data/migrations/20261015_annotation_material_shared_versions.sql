-- 子订单资料复制为独立文件及版本，允许共用不可变的上传内容。
-- 删除最后一个版本引用后才清理上传对象，不修改已有资料或文件。
DO $$
DECLARE constraint_name text;
BEGIN
  FOR constraint_name IN
    SELECT c.conname FROM pg_constraint c
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attname = 'upload_id'
    WHERE c.conrelid = 'annotation_material_version'::regclass
      AND c.contype = 'u' AND c.conkey = ARRAY[a.attnum]::smallint[]
  LOOP
    EXECUTE 'ALTER TABLE annotation_material_version DROP CONSTRAINT ' || quote_ident(constraint_name);
  END LOOP;
END $$;
CREATE INDEX IF NOT EXISTS ix_annotation_material_version_upload_id ON annotation_material_version(upload_id);
