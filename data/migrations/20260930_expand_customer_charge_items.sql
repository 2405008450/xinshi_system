-- 将子订单客户收费项扩展为母/子订单通用收费项，并补充客户对账字段。

ALTER TABLE translation_sub_order_charge_item
    ADD COLUMN IF NOT EXISTS translation_project_id UUID,
    ADD COLUMN IF NOT EXISTS billing_month VARCHAR(7),
    ADD COLUMN IF NOT EXISTS unit_price_excl_tax NUMERIC(14, 4),
    ADD COLUMN IF NOT EXISTS unit_price_incl_tax NUMERIC(14, 4),
    ADD COLUMN IF NOT EXISTS total_excl_tax NUMERIC(14, 2),
    ADD COLUMN IF NOT EXISTS total_incl_tax NUMERIC(14, 2);

ALTER TABLE translation_sub_order_charge_item
    ALTER COLUMN sub_order_id DROP NOT NULL;

UPDATE translation_sub_order_charge_item
SET unit_price_excl_tax = unit_price
WHERE unit_price_excl_tax IS NULL
  AND unit_price IS NOT NULL;

UPDATE translation_sub_order_charge_item
SET total_excl_tax = amount_override
WHERE total_excl_tax IS NULL
  AND amount_override IS NOT NULL;

UPDATE translation_sub_order_charge_item item
SET total_excl_tax = ROUND(
    metric.count_value::NUMERIC / item.unit_size * item.unit_price,
    2
)
FROM word_count_metric metric
WHERE item.total_excl_tax IS NULL
  AND item.pricing_mode = 'metric'
  AND item.sub_order_id = metric.sub_order_id
  AND metric.dimension = 'customer'
  AND item.metric_type = metric.metric_type
  AND item.unit_size IS NOT NULL
  AND item.unit_price IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_sub_order_charge_item_project'
    ) THEN
        ALTER TABLE translation_sub_order_charge_item
            ADD CONSTRAINT fk_sub_order_charge_item_project
            FOREIGN KEY (translation_project_id)
            REFERENCES translation_project(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_sub_order_charge_item_single_owner'
    ) THEN
        ALTER TABLE translation_sub_order_charge_item
            ADD CONSTRAINT ck_sub_order_charge_item_single_owner
            CHECK (num_nonnulls(translation_project_id, sub_order_id) = 1);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_sub_order_charge_item_billing_month'
    ) THEN
        ALTER TABLE translation_sub_order_charge_item
            ADD CONSTRAINT ck_sub_order_charge_item_billing_month
            CHECK (
                billing_month IS NULL
                OR billing_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_customer_charge_item_prices_nonnegative'
    ) THEN
        ALTER TABLE translation_sub_order_charge_item
            ADD CONSTRAINT ck_customer_charge_item_prices_nonnegative
            CHECK (
                (unit_price_excl_tax IS NULL OR unit_price_excl_tax >= 0)
                AND (unit_price_incl_tax IS NULL OR unit_price_incl_tax >= 0)
                AND (total_excl_tax IS NULL OR total_excl_tax >= 0)
                AND (total_incl_tax IS NULL OR total_incl_tax >= 0)
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_sub_order_charge_item_project
    ON translation_sub_order_charge_item(translation_project_id, sequence_no);
