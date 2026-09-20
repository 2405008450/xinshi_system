-- 为人才主档增加标注意愿，空值表示尚未评估。
BEGIN;

ALTER TABLE resource_person
    ADD COLUMN IF NOT EXISTS annotation_willingness VARCHAR(20);

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_resource_person_annotation_willingness'
    ) THEN
        ALTER TABLE resource_person
            ADD CONSTRAINT ck_resource_person_annotation_willingness
            CHECK (
                annotation_willingness IS NULL
                OR annotation_willingness IN ('high', 'medium', 'low')
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_resource_person_annotation_willingness
    ON resource_person (annotation_willingness);

COMMIT;
