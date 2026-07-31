BEGIN;

ALTER TABLE translation_project
    ADD COLUMN IF NOT EXISTS task_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS consultation_id UUID;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_translation_project_consultation'
    ) THEN
        ALTER TABLE translation_project
            ADD CONSTRAINT fk_translation_project_consultation
            FOREIGN KEY (consultation_id)
            REFERENCES consultation(id)
            ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_translation_project_consultation'
    ) THEN
        ALTER TABLE translation_project
            ADD CONSTRAINT uq_translation_project_consultation
            UNIQUE (consultation_id);
    END IF;
END
$$;

COMMENT ON COLUMN translation_project.task_type IS
    '项目任务类型；咨询成交建项时取 consultation.consultation_type，后续作为项目快照使用';
COMMENT ON COLUMN translation_project.consultation_id IS
    '来源咨询；一条咨询最多生成一个翻译项目';

UPDATE translation_project
SET task_type = CASE task_type
    WHEN '笔译' THEN '笔译项目'
    WHEN '口译' THEN '口译项目'
    WHEN '招聘' THEN '招聘项目'
    WHEN '设备租赁' THEN '其他项目'
    WHEN '其他' THEN '其他项目'
    ELSE task_type
END
WHERE task_type IN ('笔译', '口译', '招聘', '设备租赁', '其他');

COMMIT;
