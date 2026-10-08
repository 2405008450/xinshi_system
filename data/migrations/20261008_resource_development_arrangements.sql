-- 每日安排增量结构；重复执行不覆盖日志、工时或历史业务数据。
BEGIN;
CREATE TABLE IF NOT EXISTS resource_development_arrangement (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), work_date date NOT NULL UNIQUE,
 remarks text NOT NULL DEFAULT '', revision integer NOT NULL DEFAULT 1 CHECK(revision > 0),
 created_by uuid NOT NULL REFERENCES app_user(id), updated_by uuid NOT NULL REFERENCES app_user(id),
 created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_resource_development_arrangement_work_date ON resource_development_arrangement(work_date);
CREATE TABLE IF NOT EXISTS resource_development_arrangement_cell (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 arrangement_id uuid NOT NULL REFERENCES resource_development_arrangement(id) ON DELETE CASCADE,
 platform_id uuid NOT NULL REFERENCES resource_development_option(id), platform_name varchar(100) NOT NULL,
 owner_id uuid REFERENCES app_user(id), owner_name varchar(255) NOT NULL DEFAULT '',
 targets json NOT NULL DEFAULT '[]', projects json NOT NULL DEFAULT '[]', remarks text NOT NULL DEFAULT '',
 completed boolean NOT NULL DEFAULT false, completed_by uuid REFERENCES app_user(id),
 completed_by_name varchar(255) NOT NULL DEFAULT '', completed_at timestamp,
 UNIQUE(arrangement_id, platform_id),
 CHECK(NOT completed OR (owner_id IS NOT NULL AND completed_by IS NOT NULL AND completed_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_resource_development_arrangement_cell_arrangement_id ON resource_development_arrangement_cell(arrangement_id);
CREATE INDEX IF NOT EXISTS ix_resource_development_arrangement_cell_owner_id ON resource_development_arrangement_cell(owner_id);
COMMIT;
