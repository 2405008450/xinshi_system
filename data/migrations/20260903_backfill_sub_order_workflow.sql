-- 补齐历史子订单缺失的工作流实例。
-- 子订单创建接口此前不初始化工作流，工作流只在有人打开子订单工作流面板时才懒创建，
-- 因此从未被打开过的子订单不会出现在工作台。此处按母订单创建时的初始状态补齐。

BEGIN;

WITH missing_sub_order AS (
    SELECT s.id
    FROM translation_sub_order s
    WHERE NOT EXISTS (
        SELECT 1
        FROM workflow_instance w
        WHERE w.sub_order_id = s.id
    )
),
created_instance AS (
    INSERT INTO workflow_instance (
        sub_order_id, current_stage_key, project_status, stage_notes, stage_data
    )
    SELECT id, 'reception', 'pending', '{}'::jsonb, '{}'::jsonb
    FROM missing_sub_order
    RETURNING id
)
INSERT INTO workflow_log (
    workflow_instance_id, from_stage, to_stage, direction, description, note
)
SELECT id, '', 'reception', 'forward',
       'Workflow initialized at reception stage.',
       'System initialization'
FROM created_instance;

COMMIT;
