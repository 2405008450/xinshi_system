-- 正文图片复用附件存储，历史附件保持原有分类；迁移可重复执行。
BEGIN;
ALTER TABLE company_management_attachment
    ADD COLUMN IF NOT EXISTS is_inline_image BOOLEAN NOT NULL DEFAULT false;
COMMIT;
