-- 项目服务内容，以及支持一个项目保存多个翻译方向。
ALTER TABLE translation_project
    ADD COLUMN IF NOT EXISTS service_content VARCHAR(255);

ALTER TABLE translation_project
    ALTER COLUMN language_pair TYPE VARCHAR(500);

ALTER TABLE translation_sub_order
    ALTER COLUMN language_pair TYPE VARCHAR(500);

COMMENT ON COLUMN translation_project.service_content
    IS '本项目向客户提供的具体服务内容';

COMMENT ON COLUMN translation_project.language_pair
    IS '一个或多个规范语言对，多个值使用中文分号分隔';
