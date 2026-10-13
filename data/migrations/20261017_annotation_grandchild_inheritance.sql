BEGIN;
CREATE TABLE IF NOT EXISTS annotation_area (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    label varchar(100) NOT NULL,
    name_key varchar(100) NOT NULL UNIQUE
);
ALTER TABLE annotation_project ADD COLUMN IF NOT EXISTS area_id uuid;
-- NULL 保留历史订单独立维护；新下级订单保存显式覆盖字段列表。
ALTER TABLE annotation_project ADD COLUMN IF NOT EXISTS inheritance_overrides jsonb;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_annotation_project_area') THEN
        ALTER TABLE annotation_project ADD CONSTRAINT fk_annotation_project_area
            FOREIGN KEY (area_id) REFERENCES annotation_area(id) ON DELETE RESTRICT;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS ix_annotation_project_area ON annotation_project(area_id);
COMMIT;
