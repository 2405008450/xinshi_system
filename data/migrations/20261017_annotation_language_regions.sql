-- 语言项的地区要求只在当前订单内维护，不改变语种方向或拆单规则。
BEGIN;
ALTER TABLE annotation_project_language_item
    ADD COLUMN IF NOT EXISTS regions jsonb NOT NULL DEFAULT '[]'::jsonb;
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'annotation_project_language_item'::regclass
          AND conname = 'ck_annotation_language_regions_array'
    ) THEN
        ALTER TABLE annotation_project_language_item
            ADD CONSTRAINT ck_annotation_language_regions_array
            CHECK (jsonb_typeof(regions) = 'array');
    END IF;
END $$;
COMMIT;
