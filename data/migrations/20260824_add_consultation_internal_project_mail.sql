BEGIN;

ALTER TABLE consultation
    ADD COLUMN IF NOT EXISTS sub_client_id UUID,
    ADD COLUMN IF NOT EXISTS contact_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS customer_order_no VARCHAR(150),
    ADD COLUMN IF NOT EXISTS project_name VARCHAR(500),
    ADD COLUMN IF NOT EXISTS project_intake JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS project_intake_version INTEGER NOT NULL DEFAULT 1;

DO $$ BEGIN
    ALTER TABLE consultation ADD CONSTRAINT fk_consultation_sub_client
        FOREIGN KEY (sub_client_id) REFERENCES sub_client(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS mail_recipient_group (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500), is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS mail_recipient_group_member (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES mail_recipient_group(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE RESTRICT,
    CONSTRAINT uq_mail_group_member_user UNIQUE (group_id, user_id)
);
CREATE TABLE IF NOT EXISTS project_mail_policy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_type VARCHAR(30) NOT NULL UNIQUE,
    updated_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_project_mail_policy_type CHECK (project_type IN ('translation','interpretation','annotation','recruitment'))
);
CREATE TABLE IF NOT EXISTS project_mail_policy_group (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id UUID NOT NULL REFERENCES project_mail_policy(id) ON DELETE CASCADE,
    group_id UUID NOT NULL REFERENCES mail_recipient_group(id) ON DELETE RESTRICT,
    recipient_type VARCHAR(10) NOT NULL CHECK (recipient_type IN ('to','cc')),
    CONSTRAINT uq_project_mail_policy_group UNIQUE (policy_id, group_id, recipient_type)
);
CREATE TABLE IF NOT EXISTS business_mail (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), source_kind VARCHAR(40) NOT NULL,
    project_type VARCHAR(30) NOT NULL CHECK (project_type IN ('translation','interpretation','annotation','recruitment')),
    consultation_id UUID REFERENCES consultation(id) ON DELETE SET NULL,
    translation_project_id UUID REFERENCES translation_project(id) ON DELETE SET NULL,
    interpretation_project_id UUID REFERENCES interpretation_project(id) ON DELETE SET NULL,
    annotation_project_id UUID REFERENCES annotation_project(id) ON DELETE SET NULL,
    recruitment_project_id UUID REFERENCES recruitment_project(id) ON DELETE SET NULL,
    subject VARCHAR(1000) NOT NULL, body TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sending','sent','failed')),
    idempotency_key VARCHAR(100) NOT NULL UNIQUE, smtp_message_id VARCHAR(255) NOT NULL,
    delivery_mode VARCHAR(20), send_error TEXT,
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    send_attempted_at TIMESTAMP, sent_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS business_mail_recipient (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mail_id UUID NOT NULL REFERENCES business_mail(id) ON DELETE CASCADE,
    user_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    recipient_type VARCHAR(10) NOT NULL CHECK (recipient_type IN ('to','cc')),
    display_name_snapshot VARCHAR(255) NOT NULL, email_snapshot VARCHAR(255) NOT NULL,
    CONSTRAINT uq_business_mail_recipient_email UNIQUE (mail_id, email_snapshot)
);
CREATE TABLE IF NOT EXISTS business_mail_attempt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mail_id UUID NOT NULL REFERENCES business_mail(id) ON DELETE CASCADE,
    attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivery_mode VARCHAR(20), actual_recipients TEXT,
    success BOOLEAN NOT NULL DEFAULT FALSE, error TEXT
);
CREATE INDEX IF NOT EXISTS ix_business_mail_consultation_created ON business_mail(consultation_id, created_at);
CREATE INDEX IF NOT EXISTS ix_business_mail_project_created ON business_mail(project_type, created_at);

COMMIT;
