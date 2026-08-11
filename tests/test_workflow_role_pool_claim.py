from types import SimpleNamespace
from uuid import uuid4

import pytest

import workflow_crud


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
