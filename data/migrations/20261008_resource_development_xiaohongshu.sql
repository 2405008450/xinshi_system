-- 资源小红书号选填；旧记录使用空字符串，可重复执行。
BEGIN;
ALTER TABLE resource_development_record
  ADD COLUMN IF NOT EXISTS xiaohongshu varchar(100) NOT NULL DEFAULT '';
COMMIT;
