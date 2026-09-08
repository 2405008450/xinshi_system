BEGIN;

ALTER TABLE annotation_notice_section
    DROP CONSTRAINT IF EXISTS annotation_notice_section_sort_order_key;

ALTER TABLE annotation_notice_section
    ALTER COLUMN section_key TYPE VARCHAR(80),
    ADD COLUMN IF NOT EXISTS parent_id UUID,
    ADD COLUMN IF NOT EXISTS has_content BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS search_text TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS structure_updated_at TIMESTAMP;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_annotation_notice_section_parent_id'
    ) THEN
        ALTER TABLE annotation_notice_section
            ADD CONSTRAINT fk_annotation_notice_section_parent_id
            FOREIGN KEY (parent_id) REFERENCES annotation_notice_section(id) ON DELETE RESTRICT;
    END IF;
END $$;

UPDATE annotation_notice_section
SET title = CASE section_key
        WHEN 'customer_quote' THEN '客户报价'
        WHEN 'annotator_quote' THEN '标注员报价'
        WHEN 'trial_collection' THEN '试标/试采流程'
        WHEN 'audio_collection' THEN '音频采集流程'
        WHEN 'audio_annotation' THEN '音频标注流程'
        WHEN 'audio_evaluation' THEN '音频评测流程'
        WHEN 'text_evaluation' THEN '文本评测流程'
        WHEN 'quality_inspection' THEN '质检流程'
        WHEN 'listening_test' THEN '测听流程'
        WHEN 'slot_deduction' THEN '扣槽流程'
        WHEN 'generalization' THEN '泛化流程'
        WHEN 'translation' THEN '翻译流程'
        WHEN 'ai_evaluation' THEN 'AI评测流程'
        ELSE title
    END,
    structure_updated_at = COALESCE(structure_updated_at, CURRENT_TIMESTAMP);

INSERT INTO annotation_notice_section (
    section_key, title, sort_order, has_content, is_active, search_text, structure_updated_at
)
VALUES ('project_flow', '项目流程', 1000, FALSE, TRUE, '', CURRENT_TIMESTAMP)
ON CONFLICT (section_key) DO NOTHING;

UPDATE annotation_notice_section
SET parent_id = NULL,
    sort_order = CASE section_key
        WHEN 'customer_quote' THEN 1
        WHEN 'annotator_quote' THEN 2
        WHEN 'trial_collection' THEN 3
        WHEN 'project_flow' THEN 4
    END,
    has_content = section_key <> 'project_flow'
WHERE section_key IN ('customer_quote', 'annotator_quote', 'trial_collection', 'project_flow');

UPDATE annotation_notice_section child
SET parent_id = parent.id,
    sort_order = CASE child.section_key
        WHEN 'audio_collection' THEN 1
        WHEN 'audio_annotation' THEN 2
        WHEN 'audio_evaluation' THEN 3
        WHEN 'text_evaluation' THEN 4
        WHEN 'quality_inspection' THEN 5
        WHEN 'listening_test' THEN 6
        WHEN 'slot_deduction' THEN 7
        WHEN 'generalization' THEN 8
        WHEN 'translation' THEN 9
        WHEN 'ai_evaluation' THEN 10
    END,
    has_content = TRUE
FROM annotation_notice_section parent
WHERE parent.section_key = 'project_flow'
  AND child.section_key IN (
      'audio_collection', 'audio_annotation', 'audio_evaluation', 'text_evaluation',
      'quality_inspection', 'listening_test', 'slot_deduction', 'generalization',
      'translation', 'ai_evaluation'
  );

UPDATE annotation_notice_section section_row
SET search_text = COALESCE((
    SELECT string_agg(value #>> '{}', ' ')
    FROM jsonb_path_query(section_row.content_json, '$.**.text') AS value
), '');

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS ix_annotation_notice_section_parent_order
    ON annotation_notice_section (parent_id, sort_order);
CREATE UNIQUE INDEX IF NOT EXISTS ux_annotation_notice_active_root_order
    ON annotation_notice_section (sort_order)
    WHERE parent_id IS NULL AND is_active;
CREATE UNIQUE INDEX IF NOT EXISTS ux_annotation_notice_active_child_order
    ON annotation_notice_section (parent_id, sort_order)
    WHERE parent_id IS NOT NULL AND is_active;
CREATE INDEX IF NOT EXISTS ix_annotation_notice_title_trgm
    ON annotation_notice_section USING GIN (title gin_trgm_ops)
    WHERE is_active;
CREATE INDEX IF NOT EXISTS ix_annotation_notice_search_text_trgm
    ON annotation_notice_section USING GIN (search_text gin_trgm_ops)
    WHERE is_active AND has_content;

COMMIT;
