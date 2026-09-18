-- 人才概览语种稳定关联键。历史数据映射由 tools/audit_talent_overview_languages.py
-- 在预检后应用；本迁移只添加可重复执行的结构变更。
ALTER TABLE interpretation_language
    ADD COLUMN IF NOT EXISTS talent_overview_key VARCHAR(64);

CREATE INDEX IF NOT EXISTS ix_interpretation_language_talent_overview_key
    ON interpretation_language(talent_overview_key)
    WHERE talent_overview_key IS NOT NULL;
