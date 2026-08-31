-- 口译方向和资源需求明细支持第三至第五个有序语种；已有双语记录无需回填。

CREATE TABLE IF NOT EXISTS interpretation_project_direction_extra_language (
    direction_id UUID NOT NULL,
    sequence_no INTEGER NOT NULL,
    language_id UUID NOT NULL,
    CONSTRAINT interpretation_project_direction_extra_language_pkey
        PRIMARY KEY (direction_id, sequence_no),
    CONSTRAINT fk_interpretation_direction_extra_direction
        FOREIGN KEY (direction_id)
        REFERENCES interpretation_project_language_direction(id) ON DELETE CASCADE,
    CONSTRAINT fk_interpretation_direction_extra_language
        FOREIGN KEY (language_id)
        REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    CONSTRAINT uq_interpretation_direction_extra_language
        UNIQUE (direction_id, language_id),
    CONSTRAINT ck_interpretation_direction_extra_sequence
        CHECK (sequence_no BETWEEN 3 AND 5)
);

CREATE INDEX IF NOT EXISTS ix_interpretation_direction_extra_language
    ON interpretation_project_direction_extra_language(language_id);

CREATE TABLE IF NOT EXISTS resource_request_item_extra_language (
    item_id UUID NOT NULL,
    sequence_no INTEGER NOT NULL,
    language_id UUID NOT NULL,
    CONSTRAINT resource_request_item_extra_language_pkey
        PRIMARY KEY (item_id, sequence_no),
    CONSTRAINT fk_resource_request_item_extra_item
        FOREIGN KEY (item_id)
        REFERENCES resource_request_item(id) ON DELETE CASCADE,
    CONSTRAINT fk_resource_request_item_extra_language
        FOREIGN KEY (language_id)
        REFERENCES interpretation_language(id) ON DELETE RESTRICT,
    CONSTRAINT uq_resource_request_item_extra_language
        UNIQUE (item_id, language_id),
    CONSTRAINT ck_resource_request_item_extra_sequence
        CHECK (sequence_no BETWEEN 3 AND 5)
);

CREATE INDEX IF NOT EXISTS ix_resource_request_item_extra_language
    ON resource_request_item_extra_language(language_id);
