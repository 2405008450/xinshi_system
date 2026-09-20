-- 人才主档“工作经验”新增可选的“其他经验”字段。
ALTER TABLE resource_person
    ADD COLUMN IF NOT EXISTS other_experience TEXT;
