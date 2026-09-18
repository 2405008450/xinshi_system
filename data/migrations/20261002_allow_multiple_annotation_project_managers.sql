-- 标注项目允许配置多位项目经理；其他内部角色及其他项目类型仍保持单负责人。
ALTER TABLE project_workbench_responsibility
    DROP CONSTRAINT IF EXISTS uq_workbench_resp_annotation_role;

CREATE UNIQUE INDEX IF NOT EXISTS uq_workbench_resp_annotation_single_role
    ON project_workbench_responsibility (annotation_project_id, role_code)
    WHERE annotation_project_id IS NOT NULL
      AND role_code <> 'project_manager';

CREATE UNIQUE INDEX IF NOT EXISTS uq_workbench_resp_annotation_manager
    ON project_workbench_responsibility (annotation_project_id, role_code, assignee_id)
    WHERE annotation_project_id IS NOT NULL
      AND role_code = 'project_manager'
      AND assignee_id IS NOT NULL;
