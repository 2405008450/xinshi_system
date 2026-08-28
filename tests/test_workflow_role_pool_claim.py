from types import SimpleNamespace
from uuid import uuid4

import pytest

import workflow_crud
from models import Client, ProjectRoleAssignment, TranslationProject
from workflow_models import WorkflowInstance, WorkflowLog


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.locked = False

    def filter(self, *_args):
        return self

    def with_for_update(self):
        self.locked = True
        return self

    def all(self):
        return self.rows


class FakeDb:
    def __init__(self, rows):
        self.query_result = FakeQuery(rows)
        self.added = []
        self.committed = False

    def query(self, _model):
        return self.query_result

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True


class MultiModelDb:
    def __init__(self, rows_by_models):
        self.rows_by_models = rows_by_models
        self.added = []
        self.committed = False

    def query(self, *models):
        return MultiModelQuery(self.rows_by_models.get(models, []))

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True


class MultiModelQuery(FakeQuery):
    def join(self, *_args):
        return self

    def outerjoin(self, *_args):
        return self

    def options(self, *_args):
        return self


def test_workflow_task_assignment_type_uses_actual_assignee():
    user_id = uuid4()

    assert workflow_crud._workflow_task_assignment_type(
        SimpleNamespace(current_assignee_id=user_id), user_id
    ) == 'direct'
    assert workflow_crud._workflow_task_assignment_type(
        SimpleNamespace(current_assignee_id=None), user_id
    ) == 'role_pool'
    assert workflow_crud._workflow_task_assignment_type(
        SimpleNamespace(current_assignee_id=uuid4()), user_id
    ) == 'overview'


def test_customer_specialist_can_claim_matching_role_pool_task(monkeypatch):
    user = SimpleNamespace(id=uuid4(), full_name='测试专员', username='specialist')
    instance = SimpleNamespace(
        id=uuid4(),
        current_assignee_id=None,
        current_stage_key='reception',
        group_assign_role='客户专员',
        difficulty=None,
        updated_at=None,
    )
    db = FakeDb([instance])
    monkeypatch.setattr(workflow_crud, 'ensure_user_assignable', lambda *_args: None)
    monkeypatch.setattr(workflow_crud, 'get_user_roles_with_role_names', lambda *_args: ['客户专员'])

    result = workflow_crud.claim_role_pool_tasks(db, user, [instance.id, instance.id])

    assert result['action'] == 'role_pool_claim'
    assert result['transferred_count'] == 1
    assert instance.current_assignee_id == user.id
    assert instance.group_assign_role is None
    assert db.query_result.locked is True
    assert db.committed is True
    assert len(db.added) == 1


def test_user_cannot_claim_another_roles_pool_task(monkeypatch):
    user = SimpleNamespace(id=uuid4(), full_name='测试专员', username='specialist')
    instance = SimpleNamespace(
        id=uuid4(),
        current_assignee_id=None,
        current_stage_key='project_manager',
        group_assign_role='项目经理',
        difficulty='normal',
        updated_at=None,
    )
    db = FakeDb([instance])
    monkeypatch.setattr(workflow_crud, 'ensure_user_assignable', lambda *_args: None)
    monkeypatch.setattr(workflow_crud, 'get_user_roles_with_role_names', lambda *_args: ['客户专员'])

    with pytest.raises(PermissionError, match='不具备对应角色池权限'):
        workflow_crud.claim_role_pool_tasks(db, user, [instance.id])

    assert instance.current_assignee_id is None
    assert db.committed is False


def test_project_assistant_sees_unassigned_manuscript_responsibility_pool():
    user_id = uuid4()
    workflow = SimpleNamespace(
        id=uuid4(),
        difficulty=None,
    )
    project = SimpleNamespace(
        id=uuid4(),
        order_no='TP-ASSISTANT-001',
        project_name='待安排稿件项目',
        consultation_id=None,
        project_status='confirmed',
        customer_deadline_time=None,
        language_pair='中英',
        role_assignments=[],
    )
    client = SimpleNamespace(client_name='测试客户', client_short_name='测试')
    db = MultiModelDb({
        (WorkflowInstance, TranslationProject, Client, ProjectRoleAssignment): [
            (workflow, project, client, None)
        ],
    })

    tasks = workflow_crud._get_manuscript_responsibility_tasks(
        db,
        user_id,
        {'项目助理'},
        set(),
    )

    assert len(tasks) == 1
    assert tasks[0]['task_type'] == '稿件安排'
    assert tasks[0]['task_kind'] == 'manuscript_responsibility'
    assert tasks[0]['assignment_type'] == 'role_pool'
    assert tasks[0]['group_assign_role'] == '项目助理'


def test_project_assistant_claims_manuscript_pool_as_fixed_project_role(monkeypatch):
    user = SimpleNamespace(id=uuid4(), full_name='项目助理甲', username='assistant')
    project_id = uuid4()
    instance = SimpleNamespace(
        id=uuid4(),
        translation_project_id=project_id,
        sub_order_id=None,
        current_assignee_id=None,
        current_stage_key='reception',
        group_assign_role=None,
        difficulty='normal',
        updated_at=None,
    )
    project = SimpleNamespace(id=project_id, project_status='confirmed')
    db = MultiModelDb({
        (WorkflowInstance,): [instance],
        (TranslationProject,): [project],
        (ProjectRoleAssignment,): [],
    })
    monkeypatch.setattr(workflow_crud, 'ensure_user_assignable', lambda *_args: None)
    monkeypatch.setattr(
        workflow_crud,
        'get_user_roles_with_role_names',
        lambda *_args: ['项目助理'],
    )

    result = workflow_crud.claim_role_pool_tasks(db, user, [instance.id])

    assignments = [item for item in db.added if isinstance(item, ProjectRoleAssignment)]
    logs = [item for item in db.added if isinstance(item, WorkflowLog)]
    assert result['transferred_count'] == 1
    assert len(assignments) == 1
    assert assignments[0].translation_project_id == project_id
    assert assignments[0].role_code == 'project_assistant'
    assert assignments[0].assignee_id == user.id
    assert logs[0].direction == 'claim_project_role'
    assert len(logs[0].direction) <= WorkflowLog.__table__.c.direction.type.length
    assert instance.current_assignee_id is None
    assert db.committed is True
