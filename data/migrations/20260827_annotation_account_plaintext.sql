BEGIN;

-- 账号资产库改为明文存储。若旧表中已经存在密文，本迁移会中止，避免静默丢失数据；
-- 请先使用原密钥导出明文，或确认相关记录可删除后再执行。
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'annotation_platform_account'
          AND column_name = 'login_account_ciphertext'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM annotation_platform_account
            WHERE login_account_ciphertext IS NOT NULL OR password_ciphertext IS NOT NULL
        ) THEN
            RAISE EXCEPTION 'annotation_platform_account 中存在旧密文，无法在没有原密钥的情况下转换为明文';
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'annotation_account_password_history'
          AND column_name = 'password_ciphertext'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM annotation_account_password_history
            WHERE password_ciphertext IS NOT NULL
        ) THEN
            RAISE EXCEPTION 'annotation_account_password_history 中存在旧密文，无法在没有原密钥的情况下转换为明文';
        END IF;
    END IF;
END $$;

ALTER TABLE annotation_platform_account
    DROP CONSTRAINT IF EXISTS ck_annotation_account_registered_credential,
    DROP CONSTRAINT IF EXISTS uq_annotation_account_fingerprint,
    ADD COLUMN IF NOT EXISTS login_account TEXT,
    ADD COLUMN IF NOT EXISTS login_account_normalized TEXT,
    ADD COLUMN IF NOT EXISTS password TEXT;

ALTER TABLE annotation_platform_account
    DROP COLUMN IF EXISTS login_account_ciphertext,
    DROP COLUMN IF EXISTS login_account_fingerprint,
    DROP COLUMN IF EXISTS password_ciphertext,
    DROP COLUMN IF EXISTS encryption_key_version;

UPDATE annotation_platform_account
SET login_account_normalized = LOWER(BTRIM(login_account))
WHERE login_account IS NOT NULL AND login_account_normalized IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'annotation_platform_account'::regclass
          AND conname = 'uq_annotation_account_login_normalized'
    ) THEN
        ALTER TABLE annotation_platform_account
            ADD CONSTRAINT uq_annotation_account_login_normalized
            UNIQUE (platform_id, login_account_normalized);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'annotation_platform_account'::regclass
          AND conname = 'ck_annotation_account_registered_credential'
    ) THEN
        ALTER TABLE annotation_platform_account
            ADD CONSTRAINT ck_annotation_account_registered_credential
            CHECK (registration_status <> 'registered' OR (login_account IS NOT NULL AND password IS NOT NULL));
    END IF;
END $$;

ALTER TABLE annotation_account_password_history
    ADD COLUMN IF NOT EXISTS password TEXT;

ALTER TABLE annotation_account_password_history
    DROP COLUMN IF EXISTS password_ciphertext,
    DROP COLUMN IF EXISTS encryption_key_version;

ALTER TABLE annotation_account_password_history
    ALTER COLUMN password SET NOT NULL;

COMMIT;
