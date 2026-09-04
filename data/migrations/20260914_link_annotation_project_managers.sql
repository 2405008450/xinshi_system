-- 将历史文本型“项目经理”字段收敛到项目责任人与用户表的正式关联。
-- 仅自动迁移能唯一匹配到启用中“项目经理”角色用户的单人值；
-- 多人值和无法匹配的值继续保留在 annotation_project.custom_values 中供审计。

BEGIN;

WITH legacy_fields AS (
    SELECT id
    FROM annotation_custom_field_definition
    WHERE table_code = 'project'
      AND project_id IS NULL
      AND field_label = '项目经理'
),
unique_matches AS (
    SELECT
        ap.id AS project_id,
        min(u.id::text)::uuid AS assignee_id
    FROM annotation_project ap
    CROSS JOIN legacy_fields field
    JOIN app_user u
      ON lower(btrim(coalesce(u.full_name, ''))) = lower(btrim(ap.custom_values ->> field.id::text))
      OR lower(btrim(u.username)) = lower(btrim(ap.custom_values ->> field.id::text))
    JOIN user_role ur ON ur.user_id = u.id
    JOIN role r ON r.id = ur.role_id AND r.role_name = '项目经理'
    WHERE u.is_active IS TRUE
      AND nullif(btrim(ap.custom_values ->> field.id::text), '') IS NOT NULL
    GROUP BY ap.id
    HAVING count(DISTINCT u.id) = 1
)
INSERT INTO project_workbench_responsibility (
    id,
    annotation_project_id,
    role_code,
    assignee_id,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid(),
    matched.project_id,
    'project_manager',
    matched.assignee_id,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM unique_matches matched
ON CONFLICT (annotation_project_id, role_code) DO UPDATE
SET assignee_id = EXCLUDED.assignee_id,
    updated_at = CURRENT_TIMESTAMP
WHERE project_workbench_responsibility.assignee_id IS NULL;

UPDATE annotation_custom_field_definition
SET field_label = '历史项目经理（文本，已停用）',
    is_active = FALSE,
    updated_at = CURRENT_TIMESTAMP
WHERE table_code = 'project'
  AND project_id IS NULL
  AND field_label = '项目经理';

COMMIT;
