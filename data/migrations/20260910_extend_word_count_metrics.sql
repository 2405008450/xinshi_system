-- 笔译工作量统计新增“份数”和“页数”两个计量口径。
-- 仅放宽指标约束；现有数据和唯一索引无需变更。
ALTER TABLE word_count_metric
    DROP CONSTRAINT IF EXISTS ck_word_count_metric_type;

ALTER TABLE word_count_metric
    ADD CONSTRAINT ck_word_count_metric_type
    CHECK (
        metric_type IN (
            'words',
            'characters_no_spaces',
            'cjk_chars_korean_words',
            'foreign_words',
            'documents',
            'pages'
        )
    );
