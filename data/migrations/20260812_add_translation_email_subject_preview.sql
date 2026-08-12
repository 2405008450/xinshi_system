-- 为笔译项目保存咨询确认时生成的邮件主题快照。
ALTER TABLE translation_project
    ADD COLUMN IF NOT EXISTS email_subject_preview TEXT;
