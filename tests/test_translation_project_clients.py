from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from tests.test_translation_direction_children import case
from tests.test_chat_participant_access import environment

from crud import _attach_project_client_fields, _resolve_or_create_project_sub_client


@pytest.mark.parametrize('on_create', [True, False])
@pytest.mark.parametrize('name', ['仅填写全称的子客户有限公司', '长名称子客户' * 30])
def test_full_sub_client_name_without_short_name_is_saved_and_reloaded(case, on_create, name):
    from models import Client, SubClient
    from schemas import TranslationProjectCreate, TranslationProjectUpdate
    db, actor, crud = case
    parent = Client(client_code='CL-TEST-001', client_name='母客户全称', client_short_name='母客户')
    db.add(parent); db.commit()
    payload = dict(client_id=parent.id, sub_client_name=f'  {name}  ')
    root = crud.create_translation_project(db, TranslationProjectCreate(
        project_name='子客户回归.docx', created_by=actor.id,
        **(payload if on_create else dict(client_id=parent.id))), order_no='TP-261113-991')
    if not on_create:
        root = crud.update_translation_project(db, root.id, TranslationProjectUpdate(**payload), actor_user_id=actor.id)
    identifier = root.id
    db.expire_all()
    saved = crud.get_translation_project(db, identifier)
    assert saved.sub_client_id is not None
    assert saved.sub_client_name == name
    assert saved.sub_client_short_name == name[:100]
    assert saved.sub_client.parent_client_id == parent.id
    # 相同母客户下再次提交同一全称，应复用关联，不能重复新建。
    crud.update_translation_project(db, identifier, TranslationProjectUpdate(
        client_id=parent.id, sub_client_id=None, sub_client_name=name), actor_user_id=actor.id)
    assert db.query(SubClient).filter_by(parent_client_id=parent.id).count() == 1


def test_translation_project_response_keeps_parent_and_sub_client_separate():
    parent = SimpleNamespace(
        client_name="母客户全称",
        client_short_name="母客户",
        client_code="CL-001",
        client_manager="母客户经理",
        manager_contact="parent@example.com",
    )
    sub_client = SimpleNamespace(
        client_name="子客户全称",
        client_short_name="子客户",
        sub_client_code="CL-001.001",
        client_manager="子客户经理",
        manager_contact="sub@example.com",
    )
    project = SimpleNamespace(client=parent, sub_client=sub_client)

    _attach_project_client_fields(project)

    assert project.client_name == "母客户全称"
    assert project.client_short_name == "母客户"
    assert project.client_code == "CL-001"
    assert project.client_manager == "母客户经理"
    assert project.manager_contact == "parent@example.com"
    assert project.sub_client_name == "子客户全称"
    assert project.sub_client_short_name == "子客户"
    assert project.sub_client_code == "CL-001.001"


def test_translation_project_response_allows_parent_without_sub_client():
    parent = SimpleNamespace(
        client_name="母客户全称",
        client_short_name="母客户",
        client_code="CL-001",
        client_manager=None,
        manager_contact=None,
    )
    project = SimpleNamespace(client=parent, sub_client=None)

    _attach_project_client_fields(project)

    assert project.client_short_name == "母客户"
    assert project.sub_client_name is None
    assert project.sub_client_short_name is None
    assert project.sub_client_code is None


def test_translation_project_response_falls_back_to_sub_client_short_name():
    parent = SimpleNamespace(
        client_name="Parent full name",
        client_short_name="Parent",
        client_code="CL-001",
        client_manager=None,
        manager_contact=None,
    )
    sub_client = SimpleNamespace(
        client_name="",
        client_short_name="Child",
        sub_client_code="CL-001.001",
    )
    project = SimpleNamespace(client=parent, sub_client=sub_client)

    _attach_project_client_fields(project)

    assert project.sub_client_name == "Child"


def test_manual_sub_client_name_reuses_match_under_current_parent():
    parent_id = uuid4()
    existing_id = uuid4()
    existing = SimpleNamespace(id=existing_id)
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = existing

    resolved_id = _resolve_or_create_project_sub_client(db, parent_id, "  子客户A  ")

    assert resolved_id == existing_id
    db.add.assert_not_called()


def test_manual_sub_client_name_creates_pending_record(monkeypatch):
    parent_id = uuid4()
    generated_id = uuid4()
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    monkeypatch.setattr("crud.generate_sub_client_code", lambda *_: "CL-001.001")

    class FakeSubClient:
        parent_client_id = MagicMock()
        client_short_name = MagicMock()
        client_name = MagicMock()
        created_at = MagicMock()
        id = MagicMock()

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    monkeypatch.setattr("crud.SubClient", FakeSubClient)

    def assign_generated_id():
        db.add.call_args.args[0].id = generated_id

    db.flush.side_effect = assign_generated_id

    resolved_id = _resolve_or_create_project_sub_client(db, parent_id, "新子客户", "新子客户有限公司")

    created = db.add.call_args.args[0]
    assert resolved_id == generated_id
    assert created.parent_client_id == parent_id
    assert created.sub_client_code == "CL-001.001"
    assert created.client_name == "新子客户有限公司"
    assert created.client_short_name == "新子客户"
    assert created.client_status == "pending"
