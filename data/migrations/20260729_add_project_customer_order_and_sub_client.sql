-- 项目既保留母客户外键，也可精确关联其下的子客户。
ALTER TABLE translation_project
    ADD COLUMN IF NOT EXISTS customer_order_no VARCHAR(100);

ALTER TABLE translation_project
    ADD COLUMN IF NOT EXISTS sub_client_id UUID;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_translation_project_sub_client'
    ) THEN
        ALTER TABLE translation_project
            ADD CONSTRAINT fk_translation_project_sub_client
            FOREIGN KEY (sub_client_id)
            REFERENCES sub_client(id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_translation_project_sub_client_id
    ON translation_project(sub_client_id);

COMMENT ON COLUMN translation_project.customer_order_no
    IS '客户公司内部用于记录外包项目的客户单号';

COMMENT ON COLUMN translation_project.sub_client_id
    IS '项目实际对应的子客户；为空时直接对应母客户';
