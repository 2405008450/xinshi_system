BEGIN;

-- 数据库统一生成，覆盖表单、导入及旧译员同步；序列允许跳号，不重复使用编号。
LOCK TABLE resource_person, translator IN SHARE ROW EXCLUSIVE MODE;
CREATE SEQUENCE IF NOT EXISTS resource_person_code_seq;

CREATE OR REPLACE FUNCTION assign_resource_person_code() RETURNS trigger AS $$
DECLARE
    candidate TEXT;
    serial TEXT;
BEGIN
    IF NULLIF(btrim(NEW.resource_code), '') IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE' AND NULLIF(btrim(OLD.resource_code), '') IS NOT NULL THEN
        NEW.resource_code := OLD.resource_code;
        RETURN NEW;
    END IF;
    LOOP
        serial := nextval('resource_person_code_seq')::text;
        candidate := 'RC' || lpad(serial, greatest(6, length(serial)), '0');
        EXIT WHEN NOT EXISTS (SELECT 1 FROM resource_person WHERE resource_code = candidate)
            AND NOT EXISTS (SELECT 1 FROM translator WHERE translator_code = candidate);
    END LOOP;
    NEW.resource_code := candidate;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_resource_person_code ON resource_person;
CREATE TRIGGER trg_resource_person_code
BEFORE INSERT OR UPDATE OF resource_code ON resource_person
FOR EACH ROW EXECUTE FUNCTION assign_resource_person_code();

-- 只填补空编号；已有编号保持原值，重复执行不会重新分配。
UPDATE resource_person SET resource_code = NULL
WHERE NULLIF(btrim(resource_code), '') IS NULL;

UPDATE translator AS t SET translator_code = p.resource_code
FROM resource_person AS p
WHERE t.resource_person_id = p.id
  AND NULLIF(btrim(t.translator_code), '') IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM translator AS other
      WHERE other.translator_code = p.resource_code AND other.id <> t.id
  );

COMMIT;
