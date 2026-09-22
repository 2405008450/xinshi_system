BEGIN;

-- 籍贯独立于主要成长地，历史数据不自动填充。
ALTER TABLE resource_person ADD COLUMN IF NOT EXISTS ancestral_home VARCHAR(255);

COMMIT;
