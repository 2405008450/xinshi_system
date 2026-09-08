BEGIN;

-- sort_order 有唯一约束，先整体移到临时区间，避免原 D～K 与新顺序冲突。
UPDATE annotation_notice_section
SET sort_order = sort_order + 1000;

INSERT INTO annotation_notice_section (section_key, title, sort_order)
VALUES
    ('customer_quote', 'A. 客户报价', 1),
    ('annotator_quote', 'B. 标注员报价', 2),
    ('trial_collection', 'C. 试标/试采流程', 3),
    ('audio_collection', 'D. 音频采集流程', 4),
    ('audio_annotation', 'E. 音频标注流程', 5),
    ('audio_evaluation', 'F. 音频评测流程', 6),
    ('text_evaluation', 'G. 文本评测流程', 7),
    ('quality_inspection', 'H. 质检流程', 8),
    ('listening_test', 'I. 测听流程', 9),
    ('slot_deduction', 'J. 扣槽流程', 10),
    ('generalization', 'K. 泛化流程', 11),
    ('translation', 'L. 翻译流程', 12),
    ('ai_evaluation', 'M. AI评测流程', 13)
ON CONFLICT (section_key) DO UPDATE
SET title = EXCLUDED.title,
    sort_order = EXCLUDED.sort_order;

COMMIT;
