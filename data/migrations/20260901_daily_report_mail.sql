CREATE TABLE IF NOT EXISTS user_mail_account (
    user_id UUID PRIMARY KEY REFERENCES app_user(id) ON DELETE CASCADE,
    email_snapshot VARCHAR(255) NOT NULL,
    authorization_ciphertext BYTEA NOT NULL,
    encryption_key_version VARCHAR(50) NOT NULL,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE user_mail_account ADD COLUMN IF NOT EXISTS email_snapshot VARCHAR(255);
UPDATE user_mail_account
SET email_snapshot = app_user.email
FROM app_user
WHERE user_mail_account.user_id = app_user.id AND user_mail_account.email_snapshot IS NULL;
ALTER TABLE user_mail_account ALTER COLUMN email_snapshot SET NOT NULL;

CREATE TABLE IF NOT EXISTS daily_report_mail_policy (
    user_id UUID PRIMARY KEY REFERENCES app_user(id) ON DELETE CASCADE,
    updated_by UUID NULL REFERENCES app_user(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_report_mail_policy_group (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES daily_report_mail_policy(user_id) ON DELETE CASCADE,
    group_id UUID NOT NULL REFERENCES mail_recipient_group(id) ON DELETE RESTRICT,
    recipient_type VARCHAR(10) NOT NULL CHECK (recipient_type IN ('to','cc')),
    CONSTRAINT uq_daily_report_mail_policy_group UNIQUE (user_id, group_id, recipient_type)
);

CREATE TABLE IF NOT EXISTS daily_report_mail_delivery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES daily_report(id) ON DELETE RESTRICT,
    user_id UUID NULL REFERENCES app_user(id) ON DELETE SET NULL,
    sender_name_snapshot VARCHAR(255) NOT NULL,
    sender_email_snapshot VARCHAR(255) NOT NULL,
    subject VARCHAR(1000) NOT NULL,
    body_rows JSONB NOT NULL,
    supplemental_note TEXT NULL,
    body_html TEXT NOT NULL,
    body_text TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sending','sent','failed')),
    idempotency_key VARCHAR(100) NOT NULL UNIQUE,
    smtp_message_id VARCHAR(255) NOT NULL,
    delivery_mode VARCHAR(20) NULL,
    send_error TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    send_attempted_at TIMESTAMP NULL,
    sent_at TIMESTAMP NULL
);
CREATE INDEX IF NOT EXISTS ix_daily_report_mail_delivery_report_created
    ON daily_report_mail_delivery(report_id, created_at DESC);

CREATE TABLE IF NOT EXISTS daily_report_mail_recipient (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_id UUID NOT NULL REFERENCES daily_report_mail_delivery(id) ON DELETE CASCADE,
    user_id UUID NULL REFERENCES app_user(id) ON DELETE SET NULL,
    recipient_type VARCHAR(10) NOT NULL CHECK (recipient_type IN ('to','cc')),
    display_name_snapshot VARCHAR(255) NOT NULL,
    email_snapshot VARCHAR(255) NOT NULL,
    CONSTRAINT uq_daily_report_mail_recipient_email UNIQUE (delivery_id, email_snapshot)
);

CREATE TABLE IF NOT EXISTS daily_report_mail_attempt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_id UUID NOT NULL REFERENCES daily_report_mail_delivery(id) ON DELETE CASCADE,
    attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivery_mode VARCHAR(20) NULL,
    actual_recipients TEXT NULL,
    success BOOLEAN NOT NULL DEFAULT FALSE,
    error TEXT NULL
);
