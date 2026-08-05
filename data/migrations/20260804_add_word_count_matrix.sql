-- 将项目、子订单及译员安排的单值字数升级为多维矩阵。
BEGIN;

CREATE TABLE IF NOT EXISTS word_count_metric (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES translation_project(id) ON DELETE CASCADE,
    sub_order_id UUID REFERENCES translation_sub_order(id) ON DELETE CASCADE,
    arrangement_id UUID REFERENCES manuscript_arrangement(id) ON DELETE CASCADE,
    dimension VARCHAR(40) NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    count_value BIGINT NOT NULL,
    updated_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_word_count_metric_single_owner CHECK (num_nonnulls(project_id, sub_order_id, arrangement_id) = 1),
    CONSTRAINT ck_word_count_metric_type CHECK (metric_type IN ('words', 'characters_no_spaces', 'cjk_chars_korean_words', 'foreign_words')),
    CONSTRAINT ck_word_count_metric_dimension CHECK (dimension IN ('company', 'customer', 'translator_estimate', 'planned', 'actual')),
    CONSTRAINT ck_word_count_metric_nonnegative CHECK (count_value >= 0),
    CONSTRAINT ck_word_count_metric_owner_dimension CHECK (
        (arrangement_id IS NOT NULL AND dimension IN ('planned', 'actual')) OR
        (arrangement_id IS NULL AND dimension IN ('company', 'customer', 'translator_estimate'))
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_word_count_metric_project_dimension_type
    ON word_count_metric(project_id, dimension, metric_type) WHERE project_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_word_count_metric_sub_order_dimension_type
    ON word_count_metric(sub_order_id, dimension, metric_type) WHERE sub_order_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_word_count_metric_arrangement_dimension_type
    ON word_count_metric(arrangement_id, dimension, metric_type) WHERE arrangement_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_word_count_metric_sub_order_id ON word_count_metric(sub_order_id);
CREATE INDEX IF NOT EXISTS ix_word_count_metric_arrangement_id ON word_count_metric(arrangement_id);

-- 只迁移能够明确识别计量口径的历史值；无口径或未知口径按产品约定丢弃。
INSERT INTO word_count_metric(project_id, dimension, metric_type, count_value)
SELECT id, 'customer',
       CASE lower(trim(customer_word_count_type))
           WHEN 'words' THEN 'words' WHEN '字数' THEN 'words'
           WHEN 'characters_no_spaces' THEN 'characters_no_spaces' WHEN '字符数（不计空格）' THEN 'characters_no_spaces'
           WHEN 'cjk_chars_korean_words' THEN 'cjk_chars_korean_words' WHEN '中文字符和朝鲜语单词' THEN 'cjk_chars_korean_words'
           WHEN 'foreign_words' THEN 'foreign_words' WHEN '外文字数' THEN 'foreign_words' WHEN '外文字数（除中日韩）' THEN 'foreign_words'
       END,
       customer_word_count
FROM translation_project
WHERE customer_word_count IS NOT NULL AND customer_word_count >= 0 AND lower(trim(customer_word_count_type)) IN (
    'words', '字数', 'characters_no_spaces', '字符数（不计空格）',
    'cjk_chars_korean_words', '中文字符和朝鲜语单词', 'foreign_words', '外文字数', '外文字数（除中日韩）'
)
ON CONFLICT DO NOTHING;

INSERT INTO word_count_metric(project_id, dimension, metric_type, count_value)
SELECT id, 'company',
       CASE lower(trim(internal_word_count_type))
           WHEN 'words' THEN 'words' WHEN '字数' THEN 'words'
           WHEN 'characters_no_spaces' THEN 'characters_no_spaces' WHEN '字符数（不计空格）' THEN 'characters_no_spaces'
           WHEN 'cjk_chars_korean_words' THEN 'cjk_chars_korean_words' WHEN '中文字符和朝鲜语单词' THEN 'cjk_chars_korean_words'
           WHEN 'foreign_words' THEN 'foreign_words' WHEN '外文字数' THEN 'foreign_words' WHEN '外文字数（除中日韩）' THEN 'foreign_words'
       END,
       internal_word_count
FROM translation_project
WHERE internal_word_count IS NOT NULL AND internal_word_count >= 0 AND lower(trim(internal_word_count_type)) IN (
    'words', '字数', 'characters_no_spaces', '字符数（不计空格）',
    'cjk_chars_korean_words', '中文字符和朝鲜语单词', 'foreign_words', '外文字数', '外文字数（除中日韩）'
)
ON CONFLICT DO NOTHING;

INSERT INTO word_count_metric(project_id, dimension, metric_type, count_value)
SELECT id, 'translator_estimate',
       CASE lower(trim(expected_translator_stats_method))
           WHEN 'words' THEN 'words' WHEN '字数' THEN 'words'
           WHEN 'characters_no_spaces' THEN 'characters_no_spaces' WHEN '字符数（不计空格）' THEN 'characters_no_spaces'
           WHEN 'cjk_chars_korean_words' THEN 'cjk_chars_korean_words' WHEN '中文字符和朝鲜语单词' THEN 'cjk_chars_korean_words'
           WHEN 'foreign_words' THEN 'foreign_words' WHEN '外文字数' THEN 'foreign_words' WHEN '外文字数（除中日韩）' THEN 'foreign_words'
       END,
       expected_translator_word_count
FROM translation_project
WHERE expected_translator_word_count IS NOT NULL AND expected_translator_word_count >= 0 AND lower(trim(expected_translator_stats_method)) IN (
    'words', '字数', 'characters_no_spaces', '字符数（不计空格）',
    'cjk_chars_korean_words', '中文字符和朝鲜语单词', 'foreign_words', '外文字数', '外文字数（除中日韩）'
)
ON CONFLICT DO NOTHING;

INSERT INTO word_count_metric(sub_order_id, dimension, metric_type, count_value)
SELECT id, source.dimension,
       CASE lower(trim(source.metric_type))
           WHEN 'words' THEN 'words' WHEN '字数' THEN 'words'
           WHEN 'characters_no_spaces' THEN 'characters_no_spaces' WHEN '字符数（不计空格）' THEN 'characters_no_spaces'
           WHEN 'cjk_chars_korean_words' THEN 'cjk_chars_korean_words' WHEN '中文字符和朝鲜语单词' THEN 'cjk_chars_korean_words'
           WHEN 'foreign_words' THEN 'foreign_words' WHEN '外文字数' THEN 'foreign_words' WHEN '外文字数（除中日韩）' THEN 'foreign_words'
       END,
       source.count_value
FROM translation_sub_order tso
CROSS JOIN LATERAL (
    VALUES
        ('customer', tso.customer_word_count_type, tso.customer_word_count),
        ('company', tso.internal_word_count_type, tso.internal_word_count),
        ('translator_estimate', tso.expected_translator_stats_method, tso.expected_translator_word_count)
) AS source(dimension, metric_type, count_value)
WHERE source.count_value IS NOT NULL AND source.count_value >= 0 AND lower(trim(source.metric_type)) IN (
    'words', '字数', 'characters_no_spaces', '字符数（不计空格）',
    'cjk_chars_korean_words', '中文字符和朝鲜语单词', 'foreign_words', '外文字数', '外文字数（除中日韩）'
)
ON CONFLICT DO NOTHING;

INSERT INTO word_count_metric(arrangement_id, dimension, metric_type, count_value)
SELECT ma.id, source.dimension,
       CASE lower(trim(ma.word_count_type))
           WHEN 'words' THEN 'words' WHEN '字数' THEN 'words'
           WHEN 'characters_no_spaces' THEN 'characters_no_spaces' WHEN '字符数（不计空格）' THEN 'characters_no_spaces'
           WHEN 'cjk_chars_korean_words' THEN 'cjk_chars_korean_words' WHEN '中文字符和朝鲜语单词' THEN 'cjk_chars_korean_words'
           WHEN 'foreign_words' THEN 'foreign_words' WHEN '外文字数' THEN 'foreign_words' WHEN '外文字数（除中日韩）' THEN 'foreign_words'
       END,
       source.count_value
FROM manuscript_arrangement ma
CROSS JOIN LATERAL (VALUES ('planned', ma.planned_word_count), ('actual', ma.actual_word_count)) AS source(dimension, count_value)
WHERE source.count_value IS NOT NULL AND source.count_value >= 0 AND lower(trim(ma.word_count_type)) IN (
    'words', '字数', 'characters_no_spaces', '字符数（不计空格）',
    'cjk_chars_korean_words', '中文字符和朝鲜语单词', 'foreign_words', '外文字数', '外文字数（除中日韩）'
)
ON CONFLICT DO NOTHING;

ALTER TABLE manuscript_arrangement
    DROP CONSTRAINT IF EXISTS ck_manuscript_arrangement_planned_words,
    DROP CONSTRAINT IF EXISTS ck_manuscript_arrangement_actual_words;

ALTER TABLE translation_project
    DROP COLUMN IF EXISTS word_count,
    DROP COLUMN IF EXISTS customer_word_count,
    DROP COLUMN IF EXISTS customer_word_count_type,
    DROP COLUMN IF EXISTS internal_word_count,
    DROP COLUMN IF EXISTS internal_word_count_type,
    DROP COLUMN IF EXISTS expected_translator_stats_method,
    DROP COLUMN IF EXISTS expected_translator_word_count;

ALTER TABLE translation_sub_order
    DROP COLUMN IF EXISTS word_count,
    DROP COLUMN IF EXISTS customer_word_count,
    DROP COLUMN IF EXISTS customer_word_count_type,
    DROP COLUMN IF EXISTS internal_word_count,
    DROP COLUMN IF EXISTS internal_word_count_type,
    DROP COLUMN IF EXISTS expected_translator_stats_method,
    DROP COLUMN IF EXISTS expected_translator_word_count;

ALTER TABLE manuscript_arrangement
    DROP COLUMN IF EXISTS planned_word_count,
    DROP COLUMN IF EXISTS actual_word_count,
    DROP COLUMN IF EXISTS word_count_type;

COMMIT;
