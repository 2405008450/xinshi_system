-- 将口译需求人数下沉到每一条语言方向；无法可靠拆分的历史数据保留为空，等待人工补齐。

ALTER TABLE interpretation_project_language_direction
    ADD COLUMN IF NOT EXISTS required_count INTEGER;

ALTER TABLE consultation
    ALTER COLUMN project_intake_version SET DEFAULT 2;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_interpretation_direction_required_count'
    ) THEN
        ALTER TABLE interpretation_project_language_direction
            ADD CONSTRAINT ck_interpretation_direction_required_count
            CHECK (required_count IS NULL OR required_count > 0);
    END IF;
END $$;

WITH direction_totals AS (
    SELECT project_id, COUNT(*) AS direction_count
    FROM interpretation_project_language_direction
    GROUP BY project_id
)
UPDATE interpretation_project_language_direction direction
SET required_count = CASE
    WHEN totals.direction_count = 1 AND project.required_interpreter_count > 0
        THEN project.required_interpreter_count
    WHEN totals.direction_count > 1
         AND project.required_interpreter_count = totals.direction_count
        THEN 1
    ELSE NULL
END
FROM interpretation_project project
JOIN direction_totals totals ON totals.project_id = project.id
WHERE direction.project_id = project.id
  AND direction.required_count IS NULL;
