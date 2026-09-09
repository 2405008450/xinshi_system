-- 子订单客户收费明细与译员派稿文件选择。

CREATE TABLE IF NOT EXISTS translation_sub_order_charge_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sub_order_id UUID NOT NULL REFERENCES translation_sub_order(id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL DEFAULT 1,
    item_name VARCHAR(100) NOT NULL,
    pricing_mode VARCHAR(20) NOT NULL DEFAULT 'metric',
    metric_type VARCHAR(50),
    unit_size NUMERIC(14, 4),
    unit_price NUMERIC(14, 4),
    currency VARCHAR(3) NOT NULL DEFAULT 'CNY',
    amount_override NUMERIC(14, 2),
    remarks TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_sub_order_charge_item_mode CHECK (pricing_mode IN ('metric', 'fixed')),
    CONSTRAINT ck_sub_order_charge_item_metric CHECK (
        metric_type IS NULL OR metric_type IN (
            'words', 'characters_no_spaces', 'cjk_chars_korean_words',
            'foreign_words', 'documents', 'pages'
        )
    ),
    CONSTRAINT ck_sub_order_charge_item_unit_size CHECK (unit_size IS NULL OR unit_size > 0),
    CONSTRAINT ck_sub_order_charge_item_unit_price CHECK (unit_price IS NULL OR unit_price >= 0),
    CONSTRAINT ck_sub_order_charge_item_amount_override CHECK (amount_override IS NULL OR amount_override >= 0)
);

CREATE INDEX IF NOT EXISTS ix_sub_order_charge_item_sub_order
    ON translation_sub_order_charge_item(sub_order_id, sequence_no);

ALTER TABLE manuscript_arrangement
    ADD COLUMN IF NOT EXISTS file_selection_mode VARCHAR(20) NOT NULL DEFAULT 'legacy_all';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_manuscript_arrangement_file_selection_mode'
    ) THEN
        ALTER TABLE manuscript_arrangement
            ADD CONSTRAINT ck_manuscript_arrangement_file_selection_mode
            CHECK (file_selection_mode IN ('legacy_all', 'selected'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS manuscript_arrangement_file (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    arrangement_id UUID NOT NULL REFERENCES manuscript_arrangement(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    modified_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_manuscript_arrangement_file_path UNIQUE (arrangement_id, relative_path)
);

CREATE INDEX IF NOT EXISTS ix_manuscript_arrangement_file_arrangement
    ON manuscript_arrangement_file(arrangement_id);
