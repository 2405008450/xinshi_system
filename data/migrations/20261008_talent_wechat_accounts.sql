-- 微信账号多值与联系状态同步。旧账号原文整体保留，不拆分、不推断历史删除状态。
BEGIN;
ALTER TABLE resource_person ALTER COLUMN wechat_account TYPE text;
ALTER TABLE resource_person ADD COLUMN IF NOT EXISTS wechat_accounts json;
UPDATE resource_person SET wechat_accounts = CASE
    WHEN NULLIF(btrim(wechat_account), '') IS NULL THEN '[]'::json
    ELSE json_build_array(btrim(wechat_account)) END
WHERE wechat_accounts IS NULL;
ALTER TABLE resource_person ALTER COLUMN wechat_accounts SET DEFAULT '[]'::json;
ALTER TABLE resource_person ALTER COLUMN wechat_accounts SET NOT NULL;
ALTER TABLE resource_person ADD COLUMN IF NOT EXISTS wechat_accounts_revision integer NOT NULL DEFAULT 1;
ALTER TABLE resource_person ADD COLUMN IF NOT EXISTS wechat_contact_state json NOT NULL DEFAULT '{}'::json;
ALTER TABLE resource_development_record ADD COLUMN IF NOT EXISTS friend_accounts json NOT NULL DEFAULT '[]'::json;
ALTER TABLE resource_development_record ADD COLUMN IF NOT EXISTS contact_state json NOT NULL DEFAULT '{}'::json;
COMMIT;
