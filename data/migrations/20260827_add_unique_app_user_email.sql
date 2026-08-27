-- 用户邮箱按去除首尾空格、忽略大小写后全局唯一；空邮箱不参与约束。
CREATE UNIQUE INDEX IF NOT EXISTS uq_app_user_email_normalized
ON app_user (lower(btrim(email)))
WHERE email IS NOT NULL AND btrim(email) <> '';
