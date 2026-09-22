BEGIN;

LOCK TABLE resource_person IN SHARE ROW EXCLUSIVE MODE;

-- 保留原姓名，仅为查重生成键：忽略尾部括号补充信息，统一空白和英文大小写。
-- 不做任意子串匹配，避免把“叶问天”也标记为“叶问”的同名记录。
CREATE OR REPLACE FUNCTION resource_person_duplicate_name_key(value text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT lower(coalesce(
        nullif(btrim(regexp_replace(normalized,
            '([[:space:]　]*[(（][^()（）]*[)）][[:space:]　]*)+$', '', 'g')), ''),
        normalized
    ))
    FROM (SELECT btrim(regexp_replace(coalesce(value, ''), '[[:space:]　]+', ' ', 'g')) AS normalized) AS source;
$$;

CREATE OR REPLACE FUNCTION refresh_resource_person_name_duplicates() RETURNS trigger AS $$
BEGIN
    WITH names AS (
        SELECT id, resource_person_duplicate_name_key(full_name) AS name_key
        FROM resource_person
    ), flags AS (
        SELECT id, name_key <> '' AND
            count(*) OVER (PARTITION BY name_key) > 1 AS duplicated
        FROM names
    )
    UPDATE resource_person AS person SET name_duplicate = flags.duplicated
    FROM flags WHERE person.id = flags.id
        AND person.name_duplicate IS DISTINCT FROM flags.duplicated;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 调用已有语句级触发器，一次性刷新历史标记；原姓名和更新时间保持不变。
UPDATE resource_person SET full_name = full_name WHERE false;

COMMIT;
