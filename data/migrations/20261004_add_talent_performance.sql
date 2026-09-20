-- 扩展人才主档的结构化综合表现，并保留原 overall_rating 作为总体具体评价。
BEGIN;

ALTER TABLE resource_person
    ADD COLUMN IF NOT EXISTS overall_score INTEGER,
    ADD COLUMN IF NOT EXISTS cooperation_level VARCHAR(20),
    ADD COLUMN IF NOT EXISTS cooperation_note TEXT,
    ADD COLUMN IF NOT EXISTS punctuality_level VARCHAR(20),
    ADD COLUMN IF NOT EXISTS punctuality_note TEXT,
    ADD COLUMN IF NOT EXISTS audio_annotation_score INTEGER,
    ADD COLUMN IF NOT EXISTS audio_annotation_evaluation TEXT,
    ADD COLUMN IF NOT EXISTS non_audio_annotation_score INTEGER,
    ADD COLUMN IF NOT EXISTS non_audio_annotation_evaluation TEXT,
    ADD COLUMN IF NOT EXISTS collection_score INTEGER,
    ADD COLUMN IF NOT EXISTS collection_evaluation TEXT;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_resource_person_overall_score') THEN
        ALTER TABLE resource_person ADD CONSTRAINT ck_resource_person_overall_score
            CHECK (overall_score IS NULL OR overall_score BETWEEN 1 AND 10);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_resource_person_audio_annotation_score') THEN
        ALTER TABLE resource_person ADD CONSTRAINT ck_resource_person_audio_annotation_score
            CHECK (audio_annotation_score IS NULL OR audio_annotation_score BETWEEN 1 AND 10);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_resource_person_non_audio_annotation_score') THEN
        ALTER TABLE resource_person ADD CONSTRAINT ck_resource_person_non_audio_annotation_score
            CHECK (non_audio_annotation_score IS NULL OR non_audio_annotation_score BETWEEN 1 AND 10);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_resource_person_collection_score') THEN
        ALTER TABLE resource_person ADD CONSTRAINT ck_resource_person_collection_score
            CHECK (collection_score IS NULL OR collection_score BETWEEN 1 AND 10);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_resource_person_cooperation_level') THEN
        ALTER TABLE resource_person ADD CONSTRAINT ck_resource_person_cooperation_level
            CHECK (cooperation_level IS NULL OR cooperation_level IN ('high', 'medium', 'low'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_resource_person_punctuality_level') THEN
        ALTER TABLE resource_person ADD CONSTRAINT ck_resource_person_punctuality_level
            CHECK (punctuality_level IS NULL OR punctuality_level IN ('high', 'medium', 'low'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_resource_person_overall_score
    ON resource_person (overall_score);
CREATE INDEX IF NOT EXISTS ix_resource_person_audio_annotation_score
    ON resource_person (audio_annotation_score);
CREATE INDEX IF NOT EXISTS ix_resource_person_non_audio_annotation_score
    ON resource_person (non_audio_annotation_score);
CREATE INDEX IF NOT EXISTS ix_resource_person_collection_score
    ON resource_person (collection_score);

COMMIT;
