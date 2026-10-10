-- 岗位目标独立于语种目录；保留原有日期、账号与完成记录。
BEGIN;
ALTER TABLE resource_development_arrangement_cell
 ADD COLUMN IF NOT EXISTS role_tags json NOT NULL DEFAULT '[]';
COMMIT;
