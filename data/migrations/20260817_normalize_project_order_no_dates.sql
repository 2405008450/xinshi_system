BEGIN;

-- 统一四类项目订单号日期为 YYMMDD，与笔译项目详情使用的格式保持一致。
-- 更新前先检查转换后的订单号是否与现有数据冲突，避免唯一约束错误或数据覆盖。
DO $$
DECLARE
    conflict_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO conflict_count
    FROM (
        SELECT regexp_replace(order_no, '^([A-Z]+)-20([0-9]{6})-', '\1-\2-') AS normalized_order_no
        FROM translation_project
        WHERE order_no ~ '^TP-20[0-9]{6}-[0-9]+$'
        UNION ALL
        SELECT regexp_replace(order_no, '^([A-Z]+)-20([0-9]{6})-', '\1-\2-')
        FROM interpretation_project
        WHERE order_no ~ '^IP-20[0-9]{6}-[0-9]+$'
        UNION ALL
        SELECT regexp_replace(order_no, '^([A-Z]+)-20([0-9]{6})-', '\1-\2-')
        FROM annotation_project
        WHERE order_no ~ '^AP-20[0-9]{6}-[0-9]+$'
        UNION ALL
        SELECT regexp_replace(order_no, '^([A-Z]+)-20([0-9]{6})-', '\1-\2-')
        FROM recruitment_project
        WHERE order_no ~ '^HP-20[0-9]{6}-[0-9]+$'
    ) pending
    WHERE EXISTS (
        SELECT 1 FROM translation_project current_row WHERE current_row.order_no = pending.normalized_order_no
        UNION ALL
        SELECT 1 FROM interpretation_project current_row WHERE current_row.order_no = pending.normalized_order_no
        UNION ALL
        SELECT 1 FROM annotation_project current_row WHERE current_row.order_no = pending.normalized_order_no
        UNION ALL
        SELECT 1 FROM recruitment_project current_row WHERE current_row.order_no = pending.normalized_order_no
    );

    IF conflict_count > 0 THEN
        RAISE EXCEPTION '订单号日期格式转换存在 % 条冲突，请先处理重复订单号', conflict_count;
    END IF;

    SELECT COUNT(*) INTO conflict_count
    FROM translation_sub_order pending
    WHERE pending.sub_order_no ~ '^TP-20[0-9]{6}-[0-9]+\.[0-9]+$'
      AND EXISTS (
          SELECT 1
          FROM translation_sub_order current_row
          WHERE current_row.sub_order_no = regexp_replace(
              pending.sub_order_no,
              '^TP-20([0-9]{6})-',
              'TP-\1-'
          )
      );

    IF conflict_count > 0 THEN
        RAISE EXCEPTION '子订单号日期格式转换存在 % 条冲突，请先处理重复子订单号', conflict_count;
    END IF;
END $$;

UPDATE translation_project
SET order_no = regexp_replace(order_no, '^TP-20([0-9]{6})-', 'TP-\1-')
WHERE order_no ~ '^TP-20[0-9]{6}-[0-9]+$';

UPDATE translation_sub_order
SET sub_order_no = regexp_replace(sub_order_no, '^TP-20([0-9]{6})-', 'TP-\1-')
WHERE sub_order_no ~ '^TP-20[0-9]{6}-[0-9]+\.[0-9]+$';

UPDATE interpretation_project
SET order_no = regexp_replace(order_no, '^IP-20([0-9]{6})-', 'IP-\1-')
WHERE order_no ~ '^IP-20[0-9]{6}-[0-9]+$';

UPDATE annotation_project
SET order_no = regexp_replace(order_no, '^AP-20([0-9]{6})-', 'AP-\1-')
WHERE order_no ~ '^AP-20[0-9]{6}-[0-9]+$';

UPDATE recruitment_project
SET order_no = regexp_replace(order_no, '^HP-20([0-9]{6})-', 'HP-\1-')
WHERE order_no ~ '^HP-20[0-9]{6}-[0-9]+$';

COMMIT;
