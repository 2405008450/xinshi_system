from types import SimpleNamespace
from uuid import uuid4

import pytest

import crud
import workflow_crud
from models import AppUser, ProjectRoleAssignment, TranslationProject


class RecordingDb:
    def __init__(self):
        self.added = []
        self.deleted = []

    def add(self, value):
        self.added.append(value)

    def delete(self, value):
        self.deleted.append(value)


class SingleUserDb:
    def __init__(self, user):
        self.user = user

    def query(self, _model):
        return self

    def filter(self, *_args):
        return self

    def first(self):
        return self.user


def test_project_role_assignments_include_manager_and_empty_pools():
    manager = AppUser(id=uuid4(), full_name='经理甲', username='manager', password_hash='x')
    specialist = AppUser(id=uuid4(), full_name='专员乙', username='specialist', password_hash='x')
    project = TranslationProject(order_no='TP-TEST', project_name='测试项目')
    project.project_manager_id = manager.id
    project.project_manager = manager
    project.project_role_assignments = [
        ProjectRoleAssignment(
            role_code='project_specialist',
            assignee_id=specialist.id,
            assignee=specialist,
        )
    ]

    assignments = {item['role_code']: item for item in project.role_assignments}

    assert assignments['project_manager']['assignee_name'] == '经理甲'
    assert assignments['project_specialist']['assignee_name'] == '专员乙'
    assert assignments['project_assistant']['assignment_type'] == 'role_pool'
    assert assignments['layout_specialist']['assignee_id'] is None


def test_sync_project_roles_replaces_relation_roles(monkeypatch):
    existing = SimpleNamespace(
        role_code='project_specialist',
        assignee_id=uuid4(),
        updated_at=None,
    )
    project = SimpleNamespace(
        id=uuid4(),
        project_manager_id=None,
        project_role_assignments=[existing],
    )
    assistant_id = uuid4()
    db = RecordingDb()
    monkeypatch.setattr(crud, '_validate_project_role_assignee', lambda *_args, **_kwargs: None)

    crud._sync_project_role_assignments(db, project, [
        {'role_code': 'project_specialist', 'assignee_id': None},
        {'role_code': 'project_assistant', 'assignee_id': assistant_id},
        {'role_code': 'layout_specialist', 'assignee_id': None},
    ])

    assert db.deleted == [existing]
    assert len(db.added) == 1
    assert db.added[0].role_code == 'project_assistant'
    assert db.added[0].assignee_id == assistant_id


def test_duplicate_project_role_is_rejected():
    with pytest.raises(ValueError, match='不能重复'):
        crud._normalize_project_role_assignments([
            {'role_code': 'project_assistant', 'assignee_id': uuid4()},
            {'role_code': 'project_assistant', 'assignee_id': uuid4()},
        ])


def test_disabled_project_role_assignee_is_rejected():
    with pytest.raises(ValueError, match='不存在或已停用'):
        crud._validate_project_role_assignee(
            SingleUserDb(None),
            'project_assistant',
            uuid4(),
            require_assignable=True,
        )


def test_project_role_assignee_must_have_exact_system_role(monkeypatch):
    user = AppUser(id=uuid4(), full_name='多角色用户', username='multi', password_hash='x')
    monkeypatch.setattr(crud, 'get_user_roles_with_role_names', lambda *_args: ['项目专员'])

    with pytest.raises(ValueError, match='必须拥有“排版专员”系统角色'):
        crud._validate_project_role_assignee(
            SingleUserDb(user),
            'layout_specialist',
            user.id,
            require_assignable=False,
        )


def test_on_leave_project_role_assignee_is_rejected(monkeypatch):
    import leave_service

    user = AppUser(id=uuid4(), full_name='请假用户', username='leave', password_hash='x')
    monkeypatch.setattr(crud, 'get_user_roles_with_role_names', lambda *_args: ['项目助理'])
    monkeypatch.setattr(
        leave_service,
        'ensure_user_assignable',
        lambda *_args: (_ for _ in ()).throw(ValueError('请假中，不能分配')),
    )

    with pytest.raises(ValueError, match='请假中'):
        crud._validate_project_role_assignee(
            SingleUserDb(user),
            'project_assistant',
            user.id,
            require_assignable=True,
        )


def test_role_candidate_endpoint_uses_server_side_role_mapping(monkeypatch):
    calls = []
    expected = [SimpleNamespace(full_name='甲', username='user-a')]
    monkeypatch.setattr(
        workflow_crud,
        'get_users_by_role_names',
        lambda _db, role_names: calls.append(role_names) or expected,
    )

    assert workflow_crud.get_project_role_candidates(object(), 'layout_specialist') == expected
    assert calls == [['排版专员']]


def test_cross_role_batch_handover_is_rejected():
    instances = [
        SimpleNamespace(current_stage_key='project_specialist'),
        SimpleNamespace(current_stage_key='layout'),
    ]

    with pytest.raises(ValueError, match='同一角色类型'):
        workflow_crud._ensure_same_stage_role(instances)


def test_super_admin_cannot_bypass_normal_stage_role_check():
    assert workflow_crud._user_can_take_stage({'超级管理员'}, 'layout') is False
    assert workflow_crud._user_can_take_stage({'排版专员'}, 'layout') is True


def test_default_stage_assignment_uses_project_role(monkeypatch):
    assignee_id = uuid4()
    project = SimpleNamespace(
        project_manager_id=None,
        project_role_assignments=[
            SimpleNamespace(role_code='project_specialist', assignee_id=assignee_id)
        ],
    )
    monkeypatch.setattr(
        workflow_crud,
        '_get_parent_project_for_workflow',
        lambda *_args, **_kwargs: project,
    )
    monkeypatch.setattr(
        workflow_crud,
        '_validate_stage_assignee',
        lambda *_args, **_kwargs: SimpleNamespace(id=assignee_id),
    )

    resolved = workflow_crud._resolve_stage_assignment(
        object(),
        stage_key='project_specialist',
        project_id=uuid4(),
        sub_order_id=None,
        next_assignee_id=None,
        group_assign_role=None,
    )

    assert resolved == (assignee_id, None)


def test_unavailable_project_role_falls_back_to_exact_pool(monkeypatch):
    project = SimpleNamespace(
        project_manager_id=None,
        project_role_assignments=[
            SimpleNamespace(role_code='layout_specialist', assignee_id=uuid4())
        ],
    )
    monkeypatch.setattr(
        workflow_crud,
        '_get_parent_project_for_workflow',
        lambda *_args, **_kwargs: project,
    )
    monkeypatch.setattr(
        workflow_crud,
        '_validate_stage_assignee',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError('请假中')),
    )

    resolved = workflow_crud._resolve_stage_assignment(
        object(),
        stage_key='layout',
        project_id=uuid4(),
        sub_order_id=None,
        next_assignee_id=None,
        group_assign_role=None,
    )

    assert resolved == (None, '排版专员')
