-- 人才所在的 HR 微信/企业微信账号，兼容自主添加的账号名称。
ALTER TABLE resource_person ADD COLUMN IF NOT EXISTS wechat_account VARCHAR(100);
COMMENT ON COLUMN resource_person.wechat_account IS '所在微信（HR 微信/企业微信或自定义名称）';
