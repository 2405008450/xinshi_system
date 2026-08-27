BEGIN;

CREATE TABLE IF NOT EXISTS resource_annotation_language_skill (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id UUID NOT NULL,
    source_language_id UUID NOT NULL,
    target_language_id UUID NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_resource_annotation_language_person
        FOREIGN KEY (person_id) REFERENCES resource_person(id) ON DELETE CASCADE,
    CONSTRAINT fk_resource_annotation_language_source
        FOREIGN KEY (source_language_id) REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    CONSTRAINT fk_resource_annotation_language_target
        FOREIGN KEY (target_language_id) REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    CONSTRAINT ck_resource_annotation_language_distinct
        CHECK (target_language_id IS NULL OR source_language_id <> target_language_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_resource_annotation_language_single
    ON resource_annotation_language_skill (person_id, source_language_id)
    WHERE target_language_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_resource_annotation_language_pair
    ON resource_annotation_language_skill (person_id, source_language_id, target_language_id)
    WHERE target_language_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_resource_annotation_language_person
    ON resource_annotation_language_skill (person_id);

COMMIT;
