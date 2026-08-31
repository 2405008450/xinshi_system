ALTER TABLE resource_request
    ADD COLUMN IF NOT EXISTS demand_status VARCHAR(30) NOT NULL DEFAULT 'confirmed';

UPDATE resource_request
SET demand_status = CASE
    WHEN request_status = 'cancelled' THEN 'cancelled'
    ELSE 'confirmed'
END
WHERE demand_status IS NULL
   OR demand_status NOT IN ('draft', 'confirmed', 'cancelled');

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_resource_request_demand_status'
    ) THEN
        ALTER TABLE resource_request
            ADD CONSTRAINT ck_resource_request_demand_status
            CHECK (demand_status IN ('draft', 'confirmed', 'cancelled'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_resource_request_demand_status
    ON resource_request(demand_status, updated_at DESC);

-- PostgreSQL 会在创建视图时展开 r.*；主表新增列后必须重建视图，
-- 否则列表在视图上筛选 demand_status 会报列不存在。
DROP VIEW IF EXISTS v_resource_request_display;

CREATE VIEW v_resource_request_display AS
SELECT r.*,
       COALESCE(ap.project_status, rp.project_status, ip.project_status, tp.project_status) AS current_project_status,
       COALESCE(ap.order_no, rp.order_no, ip.order_no, tp.order_no) AS current_order_no,
       COALESCE(ap.project_name, rp.project_name, ip.project_name, tp.project_name, r.other_source_name) AS current_project_name
FROM resource_request r
LEFT JOIN annotation_project ap ON ap.id = r.annotation_project_id
LEFT JOIN recruitment_project rp ON rp.id = r.recruitment_project_id
LEFT JOIN interpretation_project ip ON ip.id = r.interpretation_project_id
LEFT JOIN translation_project tp ON tp.id = r.translation_project_id;
