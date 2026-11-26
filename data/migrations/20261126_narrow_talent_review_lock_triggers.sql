-- 收敛人才核重写锁触发器 trg_talent_review_lock 的覆盖范围：
-- 1. 移除所有不直接引用 resource_person / translator 的间接下游表上的 trg_talent_review_lock
--    （如 app_notification、chat_project_*、annotation_chat_member、财务/审批/邮件等表），
--    防止后台人才导入或核重持锁 724092401 时阻塞在线聊天发消息与通知写入。
-- 2. 移除 resource_person 上与 trg_resource_person_review_lock 重复的 trg_talent_review_lock。
-- 3. 补齐并保留所有直接外键指向 resource_person / translator 的表上的 trg_talent_review_lock。

DO $$
DECLARE
    relation regclass;
BEGIN
    -- 移除间接下游表及 resource_person 上的冗余 trg_talent_review_lock。
    FOR relation IN
        SELECT DISTINCT t.tgrelid::regclass
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        WHERE t.tgname = 'trg_talent_review_lock'
          AND NOT t.tgisinternal
          AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = current_schema())
          AND (
              c.oid = 'resource_person'::regclass
              OR NOT EXISTS (
                  SELECT 1
                  FROM pg_constraint con
                  JOIN pg_class p ON p.oid = con.confrelid
                  WHERE con.contype = 'f'
                    AND con.conrelid = c.oid
                    AND con.connamespace = c.relnamespace
                    AND p.relname IN ('resource_person', 'translator')
              )
          )
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_talent_review_lock ON %s', relation);
    END LOOP;

    -- 确保所有直接外键指向 resource_person 或 translator 的表均保留 trg_talent_review_lock。
    FOR relation IN
        SELECT DISTINCT c.conrelid::regclass
        FROM pg_constraint c
        JOIN pg_class p ON p.oid = c.confrelid
        WHERE c.contype = 'f'
          AND p.relname IN ('resource_person', 'translator')
          AND c.conrelid <> 'resource_person'::regclass
          AND c.connamespace = (SELECT oid FROM pg_namespace WHERE nspname = current_schema())
          AND NOT EXISTS (
              SELECT 1
              FROM pg_trigger t
              WHERE t.tgrelid = c.conrelid
                AND t.tgname = 'trg_talent_review_lock'
                AND NOT t.tgisinternal
          )
    LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_talent_review_lock BEFORE INSERT OR UPDATE OR DELETE ON %s FOR EACH STATEMENT EXECUTE FUNCTION lock_talent_duplicate_writes()',
            relation
        );
    END LOOP;
END $$;
