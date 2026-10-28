-- 仅供单独授权的数据库维护窗口执行；本文件不会随服务启动自动迁移。
BEGIN;
ALTER TABLE resource_development_arrangement_cell
    ADD COLUMN IF NOT EXISTS owners json NOT NULL DEFAULT '[]'::json;
UPDATE resource_development_arrangement_cell
SET owners = json_build_array(json_build_object('id', owner_id::text, 'name', owner_name))
WHERE owner_id IS NOT NULL AND (owners IS NULL OR owners::jsonb = '[]'::jsonb);
COMMIT;
