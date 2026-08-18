-- 标注项目客户单价币种改为可留空；人民币为默认使用场景，不再强制填写或展示。
ALTER TABLE annotation_project_price_item ALTER COLUMN currency DROP NOT NULL;
ALTER TABLE annotation_project_price_item ALTER COLUMN currency DROP DEFAULT;
UPDATE annotation_project_price_item SET currency = NULL WHERE currency = 'CNY';
