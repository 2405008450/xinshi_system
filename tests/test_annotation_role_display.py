"""角色摘要回归：全部使用内存对象，不连接业务数据库。"""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from annotation_models import AnnotationProject
from project_workbench_service import role_assignments_for_project
from test_annotation_customer_progress import environment


def responsibility(user_id=None, name=None, role='project_manager'):
    return SimpleNamespace(role_code=role, assignee_id=user_id,
                           assignee=SimpleNamespace(full_name=name, username='fallback') if user_id else None)


@pytest.mark.parametrize('assigned_count', [0, 1, 2])
def test_model_and_service_ignore_duplicate_pool_rows_and_preserve_managers(assigned_count, monkeypatch):
    managers = [responsibility(uuid4(), f'经理{i}') for i in range(assigned_count)]
    rows = [responsibility() for _ in range(12)] + managers + managers
    project = SimpleNamespace(workbench_responsibilities=rows)

    class Query:
        def options(self, *_): return self
        def filter(self, *_): return self
        def all(self): return rows

    db = SimpleNamespace(query=lambda *_: Query())
    monkeypatch.setattr('project_workbench_service.joinedload', lambda *_: None)
    outputs = [AnnotationProject.role_assignments.fget(project), role_assignments_for_project(db, 'annotation', uuid4())]
    assert outputs[0] == outputs[1]
    for result in outputs:
        manager_rows = [row for row in result if row['role_code'] == 'project_manager']
        assert len(manager_rows) == max(1, assigned_count)
        assert [row['assignee_id'] for row in manager_rows] == ([row.assignee_id for row in managers] or [None])
        assert [row['assignment_type'] for row in manager_rows] == (['direct'] * assigned_count or ['role_pool'])
        assert [row['role_code'] for row in result[-2:]] == ['project_specialist', 'project_assistant']


def test_missing_roles_still_have_one_pool_placeholder_each():
    result = AnnotationProject.role_assignments.fget(SimpleNamespace(workbench_responsibilities=[]))
    assert len(result) == 3
    assert all(row['assignee_id'] is None and row['assignment_type'] == 'role_pool' for row in result)


def test_annotation_role_backfill_is_idempotent(environment):
    import ast
    from pathlib import Path
    from sqlalchemy import text
    from workflow_models import ProjectWorkbenchResponsibility

    db, users, project, child, _ = environment
    # 直接执行启动入口使用的 SQL，验证多次补齐不会给已分配经理追加空行。
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8'))
    sql = next(node.value for node in ast.walk(tree)
               if isinstance(node, ast.Constant) and isinstance(node.value, str)
               and node.value.strip().startswith('INSERT INTO project_workbench_responsibility (annotation_project_id, role_code)'))
    for user in users[:2]:
        db.add(ProjectWorkbenchResponsibility(annotation_project_id=project.id,
               role_code='project_manager', assignee_id=user.id))
    db.flush()
    for _ in range(3):
        db.execute(text(sql))
    rows = db.query(ProjectWorkbenchResponsibility).filter_by(annotation_project_id=project.id).all()
    assert len(rows) == 4
    assert {row.assignee_id for row in rows if row.role_code == 'project_manager'} == {user.id for user in users[:2]}
    empty_rows = db.query(ProjectWorkbenchResponsibility).filter_by(annotation_project_id=child.id).all()
    assert len(empty_rows) == 3
    assert all(row.assignee_id is None for row in empty_rows)
