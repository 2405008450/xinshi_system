BEGIN;

LOCK TABLE resource_person IN SHARE ROW EXCLUSIVE MODE;
ALTER TABLE resource_person ADD COLUMN IF NOT EXISTS name_duplicate boolean NOT NULL DEFAULT false;

-- 仅在人才新增、删除或姓名写入时重算；分页、筛选和其他字段编辑只读取标记。
CREATE OR REPLACE FUNCTION refresh_resource_person_name_duplicates() RETURNS trigger AS $$
BEGIN
    WITH flags AS (
        SELECT id, btrim(full_name) <> '' AND
            count(*) OVER (PARTITION BY btrim(full_name)) > 1 AS duplicated
        FROM resource_person
    )
    UPDATE resource_person AS person SET name_duplicate = flags.duplicated
    FROM flags WHERE person.id = flags.id
        AND person.name_duplicate IS DISTINCT FROM flags.duplicated;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 同名并发写入必须串行完成检查，避免两个事务都未看到对方的新记录。
CREATE OR REPLACE FUNCTION lock_resource_person_name_duplicates() RETURNS trigger AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(728104, 12);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_resource_person_name_lock ON resource_person;
CREATE TRIGGER trg_resource_person_name_lock
BEFORE INSERT OR DELETE OR UPDATE OF full_name ON resource_person
FOR EACH STATEMENT EXECUTE FUNCTION lock_resource_person_name_duplicates();

DROP TRIGGER IF EXISTS trg_resource_person_name_duplicates ON resource_person;
CREATE TRIGGER trg_resource_person_name_duplicates
AFTER INSERT OR DELETE OR UPDATE OF full_name ON resource_person
FOR EACH STATEMENT EXECUTE FUNCTION refresh_resource_person_name_duplicates();

-- 初始化历史记录；重复执行迁移不会修改姓名或更新时间。
WITH flags AS (
    SELECT id, btrim(full_name) <> '' AND
        count(*) OVER (PARTITION BY btrim(full_name)) > 1 AS duplicated
    FROM resource_person
)
UPDATE resource_person AS person SET name_duplicate = flags.duplicated
FROM flags WHERE person.id = flags.id
    AND person.name_duplicate IS DISTINCT FROM flags.duplicated;

COMMIT;
