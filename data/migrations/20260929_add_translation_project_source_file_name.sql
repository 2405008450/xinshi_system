-- 为笔译母订单保存独立的真实文件名称，供无子订单场景及后续财务对账使用。

ALTER TABLE translation_project
    ADD COLUMN IF NOT EXISTS source_file_name VARCHAR(255);

COMMENT ON COLUMN translation_project.source_file_name IS
    '母订单对应的真实源文件名称；与自动生成的项目名称分离';
