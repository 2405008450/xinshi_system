-- 咨询方式补充说明：保留下拉选项用于筛选，详细号码、邮箱、平台或联系人单独存储。

ALTER TABLE consultation
    ADD COLUMN IF NOT EXISTS consultation_method_detail VARCHAR(255);
