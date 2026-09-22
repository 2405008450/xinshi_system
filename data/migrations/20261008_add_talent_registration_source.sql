-- 人才登记来源：记录资源整合行动、批量导入批次或其他招募渠道。
ALTER TABLE resource_person ADD COLUMN IF NOT EXISTS registration_source VARCHAR(255);
COMMENT ON COLUMN resource_person.registration_source IS '人才登记来源或资源整合批次';
