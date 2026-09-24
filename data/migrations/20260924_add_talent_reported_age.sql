-- 原表只提供年龄时独立保存，不反推出生年月；已知生日时优先计算年龄。
ALTER TABLE resource_person ADD COLUMN IF NOT EXISTS reported_age INTEGER;
