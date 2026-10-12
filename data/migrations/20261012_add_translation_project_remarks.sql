-- 笔译母项目的通用备注；保留历史记录为空，不复用子订单或稿件安排备注。
ALTER TABLE public.translation_project
    ADD COLUMN IF NOT EXISTS remarks TEXT;

COMMENT ON COLUMN public.translation_project.remarks IS
    '笔译母项目备注，与子订单及稿件安排备注独立保存';
