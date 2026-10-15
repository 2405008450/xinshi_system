-- 暂停只扩展生命周期约束，不修改存量业务记录。
DO $$
BEGIN
    ALTER TABLE resource_request DROP CONSTRAINT IF EXISTS ck_resource_request_demand_status;
    ALTER TABLE resource_request ADD CONSTRAINT ck_resource_request_demand_status
        CHECK (demand_status IN ('draft', 'confirmed', 'paused', 'cancelled'));
END
$$;
