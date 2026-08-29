-- 为五类核心创建接口增加服务端幂等键。
-- nullable 唯一列允许历史记录保持 NULL；同一键只能成功创建一条记录。

ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);
ALTER TABLE interpretation_project ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);
ALTER TABLE annotation_project ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);
ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);
ALTER TABLE resource_request ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_translation_project_idempotency_key') THEN
        ALTER TABLE translation_project ADD CONSTRAINT uq_translation_project_idempotency_key UNIQUE (idempotency_key);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_interpretation_project_idempotency_key') THEN
        ALTER TABLE interpretation_project ADD CONSTRAINT uq_interpretation_project_idempotency_key UNIQUE (idempotency_key);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_annotation_project_idempotency_key') THEN
        ALTER TABLE annotation_project ADD CONSTRAINT uq_annotation_project_idempotency_key UNIQUE (idempotency_key);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_recruitment_project_idempotency_key') THEN
        ALTER TABLE recruitment_project ADD CONSTRAINT uq_recruitment_project_idempotency_key UNIQUE (idempotency_key);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_resource_request_idempotency_key') THEN
        ALTER TABLE resource_request ADD CONSTRAINT uq_resource_request_idempotency_key UNIQUE (idempotency_key);
    END IF;
END $$;
