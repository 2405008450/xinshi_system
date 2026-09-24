-- 微信群与联系账号分别保存，一行一个群，保留原始群名和状态说明。
ALTER TABLE resource_person ADD COLUMN IF NOT EXISTS wechat_groups TEXT;
