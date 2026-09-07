BEGIN;

CREATE TABLE IF NOT EXISTS annotation_notice_section (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_key VARCHAR(40) NOT NULL UNIQUE,
    title VARCHAR(100) NOT NULL,
    sort_order INTEGER NOT NULL UNIQUE,
    content_json JSONB,
    updated_by UUID,
    updated_at TIMESTAMP,
    CONSTRAINT fk_annotation_notice_section_updated_by
        FOREIGN KEY (updated_by) REFERENCES app_user(id) ON DELETE SET NULL
);

INSERT INTO annotation_notice_section (section_key, title, sort_order)
VALUES
    ('customer_quote', 'A. 客户报价', 1),
    ('annotator_quote', 'B. 标注员报价', 2),
    ('trial_collection', 'C. 试标/试采流程', 3),
    ('audio_annotation', 'D. 音频标注流程', 4),
    ('audio_evaluation', 'E. 音频评测流程', 5),
    ('text_evaluation', 'F. 文本评测流程', 6),
    ('quality_inspection', 'G. 质检流程', 7),
    ('listening_test', 'H. 测听流程', 8),
    ('slot_deduction', 'I. 扣槽流程', 9),
    ('generalization', 'J. 泛化流程', 10),
    ('translation', 'K. 翻译流程', 11)
ON CONFLICT (section_key) DO UPDATE
SET title = EXCLUDED.title,
    sort_order = EXCLUDED.sort_order;

COMMIT;
