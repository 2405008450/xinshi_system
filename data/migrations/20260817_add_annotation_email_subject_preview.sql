-- 标注项目新增可编辑、可持久化的邮件主题预览。
ALTER TABLE annotation_project
    ADD COLUMN IF NOT EXISTS email_subject_preview VARCHAR(1000);
