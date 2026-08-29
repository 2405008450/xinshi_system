-- 为客户、子客户、客户联系人、人才和笔译子订单增加服务端幂等键。

ALTER TABLE client ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);
ALTER TABLE sub_client ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);
ALTER TABLE client_contact ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);
ALTER TABLE resource_person ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);
ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_client_idempotency_key') THEN
        ALTER TABLE client ADD CONSTRAINT uq_client_idempotency_key UNIQUE (idempotency_key);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_sub_client_idempotency_key') THEN
        ALTER TABLE sub_client ADD CONSTRAINT uq_sub_client_idempotency_key UNIQUE (idempotency_key);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_client_contact_idempotency_key') THEN
        ALTER TABLE client_contact ADD CONSTRAINT uq_client_contact_idempotency_key UNIQUE (idempotency_key);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_resource_person_idempotency_key') THEN
        ALTER TABLE resource_person ADD CONSTRAINT uq_resource_person_idempotency_key UNIQUE (idempotency_key);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_translation_sub_order_idempotency_key') THEN
        ALTER TABLE translation_sub_order ADD CONSTRAINT uq_translation_sub_order_idempotency_key UNIQUE (idempotency_key);
    END IF;
END $$;
