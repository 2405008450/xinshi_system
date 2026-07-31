-- 将字数按“统计来源”和“计量口径”拆分，同时保留旧 word_count 字段兼容历史数据。
ALTER TABLE translation_project
    ADD COLUMN IF NOT EXISTS customer_word_count BIGINT,
    ADD COLUMN IF NOT EXISTS customer_word_count_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS internal_word_count BIGINT,
    ADD COLUMN IF NOT EXISTS internal_word_count_type VARCHAR(50);

ALTER TABLE translation_sub_order
    ADD COLUMN IF NOT EXISTS customer_word_count BIGINT,
    ADD COLUMN IF NOT EXISTS customer_word_count_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS internal_word_count BIGINT,
    ADD COLUMN IF NOT EXISTS internal_word_count_type VARCHAR(50);

ALTER TABLE manuscript_arrangement
    ADD COLUMN IF NOT EXISTS word_count_type VARCHAR(50);
