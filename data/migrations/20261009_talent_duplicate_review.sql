-- 仅在明确授权的目标数据库手动执行；常驻服务不自动执行本迁移。
BEGIN;
SET LOCAL lock_timeout = '5s';
SELECT pg_advisory_xact_lock(724092401);
ALTER TABLE resource_person ADD COLUMN IF NOT EXISTS archived_into_id uuid;
ALTER TABLE resource_person ADD COLUMN IF NOT EXISTS archived_at timestamptz;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_resource_person_archive' AND conrelid='resource_person'::regclass) THEN
        ALTER TABLE resource_person ADD CONSTRAINT fk_resource_person_archive
            FOREIGN KEY (archived_into_id) REFERENCES resource_person(id) ON DELETE RESTRICT;
        ALTER TABLE resource_person ADD CONSTRAINT ck_resource_person_archive_self
            CHECK (archived_into_id IS NULL OR archived_into_id <> id);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS ix_resource_person_archived_into ON resource_person(archived_into_id);

CREATE TABLE IF NOT EXISTS talent_duplicate_operation (
    id uuid PRIMARY KEY,
    idempotency_key varchar(128) NOT NULL UNIQUE,
    request_hash varchar(64) NOT NULL,
    action varchar(20) NOT NULL CHECK (action IN ('different','defer','keep','merge')),
    name_key text NOT NULL,
    person_ids json NOT NULL,
    target_id uuid,
    actor_id uuid NOT NULL,
    actor_name varchar(255) NOT NULL,
    decisions json NOT NULL,
    before_snapshot json NOT NULL,
    after_snapshot json NOT NULL,
    comparison_fingerprint varchar(64) NOT NULL,
    created_at timestamptz NOT NULL,
    undone_at timestamptz,
    undone_by uuid
);
CREATE INDEX IF NOT EXISTS ix_talent_duplicate_operation_name_key ON talent_duplicate_operation(name_key);
CREATE INDEX IF NOT EXISTS ix_talent_duplicate_operation_created ON talent_duplicate_operation(created_at DESC);

CREATE OR REPLACE FUNCTION resource_person_duplicate_name_key(value text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT lower(coalesce(nullif(btrim(regexp_replace(normalized,
        '([[:space:]　]*[(（][^()（）]*[)）][[:space:]　]*)+$', '', 'g')), ''), normalized))
    FROM (SELECT btrim(regexp_replace(coalesce(value, ''), '[[:space:]　]+', ' ', 'g')) AS normalized) AS source;
$$;
CREATE INDEX IF NOT EXISTS ix_resource_person_review_name_key
    ON resource_person(resource_person_duplicate_name_key(full_name)) WHERE archived_into_id IS NULL;

CREATE OR REPLACE FUNCTION refresh_resource_person_name_duplicates() RETURNS trigger AS $$
BEGIN
    WITH flags AS (
        SELECT id, archived_into_id IS NULL AND resource_person_duplicate_name_key(full_name) <> '' AND
            count(*) FILTER (WHERE archived_into_id IS NULL)
            OVER (PARTITION BY resource_person_duplicate_name_key(full_name)) > 1 AS duplicated
        FROM resource_person
    )
    UPDATE resource_person AS person SET name_duplicate = flags.duplicated
    FROM flags WHERE person.id = flags.id AND person.name_duplicate IS DISTINCT FROM flags.duplicated;
    RETURN NULL;
END $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION lock_talent_duplicate_writes() RETURNS trigger AS $$
BEGIN
    -- 与现有公司账号编辑共用锁，保证预览提交时所有档案及关联快照一致。
    PERFORM pg_advisory_xact_lock(724092401);
    RETURN NULL;
END $$ LANGUAGE plpgsql;
CREATE OR REPLACE FUNCTION lock_resource_person_name_duplicates() RETURNS trigger AS $$
BEGIN
    -- 先公司账号/核重锁，后姓名锁，避免与普通编辑入口形成反向加锁死锁。
    PERFORM pg_advisory_xact_lock(724092401);
    PERFORM pg_advisory_xact_lock(728104, 12);
    RETURN NULL;
END $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION guard_talent_archive() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.archived_into_id IS NOT NULL OR EXISTS (SELECT 1 FROM resource_person WHERE archived_into_id=OLD.id) THEN
            RAISE EXCEPTION '人才有归档追溯关系，不能删除';
        END IF;
        RETURN OLD;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.archived_into_id IS NOT NULL AND NEW.archived_into_id IS NOT DISTINCT FROM OLD.archived_into_id
       AND (to_jsonb(NEW) - 'name_duplicate') IS DISTINCT FROM (to_jsonb(OLD) - 'name_duplicate') THEN
        RAISE EXCEPTION '归档人才只读，请修改保留档案';
    END IF;
    IF NEW.archived_into_id IS NOT NULL AND EXISTS (SELECT 1 FROM resource_person WHERE id=NEW.archived_into_id AND archived_into_id IS NOT NULL) THEN
        RAISE EXCEPTION '归档目标必须为有效主档';
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION guard_talent_owned_record() RETURNS trigger AS $$
DECLARE owner uuid;
BEGIN
    owner := CASE WHEN TG_OP='DELETE' THEN OLD.person_id ELSE NEW.person_id END;
    IF EXISTS (SELECT 1 FROM resource_person WHERE id=owner AND archived_into_id IS NOT NULL) THEN
        RAISE EXCEPTION '归档人才明细和附件只读';
    END IF;
    IF TG_OP='UPDATE' AND OLD.person_id IS DISTINCT FROM NEW.person_id AND EXISTS
       (SELECT 1 FROM resource_person WHERE id=OLD.person_id AND archived_into_id IS NOT NULL) THEN
        RAISE EXCEPTION '不能移动归档人才的原始明细';
    END IF;
    RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION guard_talent_new_reference() RETURNS trigger AS $$
DECLARE selected uuid; old_selected uuid; owner uuid;
BEGIN
    selected := (to_jsonb(NEW)->>TG_ARGV[0])::uuid;
    IF TG_OP='UPDATE' THEN
        old_selected := (to_jsonb(OLD)->>TG_ARGV[0])::uuid;
        IF selected IS NOT DISTINCT FROM old_selected THEN RETURN NEW; END IF;
    END IF;
    owner := selected;
    IF TG_ARGV[1]='translator' THEN
        SELECT coalesce(resource_person_id,id) INTO owner FROM translator WHERE id=selected;
    END IF;
    IF EXISTS (SELECT 1 FROM resource_person WHERE id=owner AND archived_into_id IS NOT NULL) THEN
        RAISE EXCEPTION '新业务关联不能选择归档人才，请选择保留档案';
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_resource_person_review_guard ON resource_person;
CREATE TRIGGER trg_resource_person_review_guard BEFORE INSERT OR UPDATE OR DELETE ON resource_person
    FOR EACH ROW EXECUTE FUNCTION guard_talent_archive();
DROP TRIGGER IF EXISTS trg_resource_person_review_lock ON resource_person;
CREATE TRIGGER trg_resource_person_review_lock BEFORE INSERT OR UPDATE OR DELETE ON resource_person
    FOR EACH STATEMENT EXECUTE FUNCTION lock_talent_duplicate_writes();
DROP TRIGGER IF EXISTS trg_resource_person_name_duplicates ON resource_person;
CREATE TRIGGER trg_resource_person_name_duplicates AFTER INSERT OR DELETE OR UPDATE OF full_name, archived_into_id ON resource_person
    FOR EACH STATEMENT EXECUTE FUNCTION refresh_resource_person_name_duplicates();

DO $$ DECLARE relation regclass; table_name text; fk record; BEGIN
    -- 真实业务关联及下游明细写入也参与串行化，历史外键保持原值。
    FOR relation IN
        WITH RECURSIVE linked(oid) AS (
            SELECT 'resource_person'::regclass::oid
            UNION
            SELECT c.conrelid FROM pg_constraint c JOIN linked p ON c.confrelid=p.oid WHERE c.contype='f'
        ) SELECT oid::regclass FROM linked
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_talent_review_lock ON %s', relation);
        EXECUTE format('CREATE TRIGGER trg_talent_review_lock BEFORE INSERT OR UPDATE OR DELETE ON %s FOR EACH STATEMENT EXECUTE FUNCTION lock_talent_duplicate_writes()', relation);
    END LOOP;
    FOREACH table_name IN ARRAY ARRAY['resource_capability','resource_written_translation_profile','resource_interpretation_profile',
        'resource_annotation_profile','resource_annotation_language_skill','resource_career_profile','resource_education_experience',
        'resource_language_skill','resource_certificate','resource_person_attachment']
    LOOP
        relation := to_regclass(table_name);
        IF relation IS NOT NULL THEN
            EXECUTE format('DROP TRIGGER IF EXISTS trg_talent_owned_guard ON %s', relation);
            EXECUTE format('CREATE TRIGGER trg_talent_owned_guard BEFORE INSERT OR UPDATE OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION guard_talent_owned_record()', relation);
        END IF;
    END LOOP;
    FOR fk IN SELECT c.conrelid::regclass AS relation, a.attname AS column_name, p.relname AS parent
        FROM pg_constraint c JOIN pg_class p ON p.oid=c.confrelid
        JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
        WHERE c.contype='f' AND array_length(c.conkey,1)=1 AND p.relname IN ('resource_person','translator')
        AND c.conrelid <> 'resource_person'::regclass
        AND c.connamespace=(SELECT oid FROM pg_namespace WHERE nspname=current_schema())
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON %s', 'trg_talent_ref_' || fk.column_name, fk.relation);
        EXECUTE format('CREATE TRIGGER %I BEFORE INSERT OR UPDATE OF %I ON %s FOR EACH ROW EXECUTE FUNCTION guard_talent_new_reference(%L,%L)',
            'trg_talent_ref_' || fk.column_name, fk.column_name, fk.relation, fk.column_name, fk.parent);
    END LOOP;
END $$;
-- 刷新标记，不变更原姓名和业务更新时间。
UPDATE resource_person SET full_name=full_name WHERE false;
COMMIT;
