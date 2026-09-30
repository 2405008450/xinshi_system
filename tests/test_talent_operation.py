from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import resource_service as service
from resource_schemas import ResourcePersonCreate, ResourcePersonUpdate


@pytest.mark.parametrize("full_name,expected", [("操作员", "操作员"), (None, "operator"), ("  ", "operator")])
def test_operation_uses_name_snapshot(full_name, expected):
    actor = SimpleNamespace(id=uuid4(), full_name=full_name, username="operator")
    person = SimpleNamespace()
    service._record_talent_operation(person, actor)
    assert person.operated_by == actor.id
    assert person.operator_name == expected
    assert isinstance(person.operated_at, datetime)
    actor.full_name = "改名"
    assert person.operator_name == expected


@pytest.mark.parametrize("kind", ["name", "status"])
def test_inline_operation_only_changes_on_actual_write(monkeypatch, kind):
    previous_time = datetime(2020, 1, 1)
    person = SimpleNamespace(id=uuid4(), full_name="原姓名", status="standby",
                             operator_name="原操作员", operated_at=previous_time)
    actor = SimpleNamespace(id=uuid4(), full_name="新操作员", username="new")
    commits = []
    db = SimpleNamespace(flush=lambda: None, commit=lambda: commits.append(True))
    monkeypatch.setattr(service, "get_talent", lambda *_: person)
    monkeypatch.setattr(service, "_sync_legacy_translator", lambda *_: None)
    function = service.update_talent_name if kind == "name" else service.update_talent_status
    function(db, person.id, person.full_name if kind == "name" else person.status, actor=actor)
    assert person.operated_at == previous_time
    assert person.operator_name == "原操作员"
    assert not commits
    function(db, person.id, "新姓名" if kind == "name" else "active", actor=actor)
    assert person.operated_by == actor.id
    assert person.operator_name == "新操作员"
    assert person.operated_at > previous_time
    assert len(commits) == 1


@pytest.mark.parametrize("schema", [ResourcePersonCreate, ResourcePersonUpdate])
def test_operation_fields_cannot_be_supplied_by_client(schema):
    payload = schema(full_name="人员", operator_name="伪造", operated_by=str(uuid4()),
                     operated_at="2020-01-01T00:00:00")
    assert not {"operator_name", "operated_by", "operated_at"} & payload.model_dump().keys()


@pytest.mark.parametrize("recruitment", [False, True])
def test_full_save_records_actor(monkeypatch, recruitment):
    person = SimpleNamespace(id=uuid4(), resource_code="R1", career_profile=None)
    actor = SimpleNamespace(id=uuid4(), full_name="保存人", username="save")
    monkeypatch.setattr(service, "get_talent", lambda *_: person)
    monkeypatch.setattr(service, "find_duplicate_talents", lambda *_, **__: [])
    for name in ("_sync_capabilities", "_sync_profiles", "_sync_annotation_language_skills",
                 "_sync_owned_collections", "_sync_display_name", "_sync_legacy_translator"):
        monkeypatch.setattr(service, name, lambda *_: None)
    db = SimpleNamespace(flush=lambda: None, commit=lambda: None)
    function = service.update_recruitment_talent if recruitment else service.update_talent
    function(db, person.id, ResourcePersonUpdate(full_name="人员"), actor=actor)
    assert person.operated_by == actor.id
    assert person.operator_name == "保存人"
    assert isinstance(person.operated_at, datetime)


def test_create_records_actor_before_commit(monkeypatch):
    actor = SimpleNamespace(id=uuid4(), full_name="录入人", username="create")
    saved = []
    monkeypatch.setattr(service, "ResourcePerson", lambda **values: SimpleNamespace(id=uuid4(), **values))
    monkeypatch.setattr(service, "find_duplicate_talents", lambda *_, **__: [])
    for name in ("_sync_capabilities", "_sync_profiles", "_sync_annotation_language_skills",
                 "_sync_owned_collections", "_sync_display_name", "_sync_legacy_translator"):
        monkeypatch.setattr(service, name, lambda *_: None)
    monkeypatch.setattr(service, "get_talent", lambda *_: saved[0])
    db = SimpleNamespace(add=lambda person: saved.append(person), flush=lambda: None,
                         commit=lambda: None)
    person = service.create_talent(db, ResourcePersonCreate(full_name="新人才"), actor=actor)
    assert person.operated_by == actor.id
    assert person.operator_name == "录入人"
    assert isinstance(person.operated_at, datetime)


def test_duplicate_failure_preserves_operation(monkeypatch):
    previous_time = datetime(2020, 1, 1)
    person = SimpleNamespace(id=uuid4(), operator_name="原操作员", operated_at=previous_time)
    monkeypatch.setattr(service, "get_talent", lambda *_: person)
    monkeypatch.setattr(service, "find_duplicate_talents", lambda *_, **__: [{"id": str(uuid4())}])
    actor = SimpleNamespace(id=uuid4(), full_name="新操作员", username="new")
    with pytest.raises(service.TalentDuplicateError):
        service.update_talent(object(), person.id, ResourcePersonUpdate(full_name="人员"), actor=actor)
    assert person.operator_name == "原操作员"
    assert person.operated_at == previous_time


def test_idempotent_create_keeps_original_operator(monkeypatch):
    from routers import talents

    person = SimpleNamespace(id=uuid4(), operator_name="原录入人", operated_at=datetime(2020, 1, 1))
    query = SimpleNamespace(filter=lambda *_: query, first=lambda: person)
    db = SimpleNamespace(query=lambda *_: query)
    monkeypatch.setattr(talents, "can_view_talent_contacts", lambda *_: True)
    monkeypatch.setattr(talents, "get_talent", lambda *_: person)
    monkeypatch.setattr(talents, "serialize_with_contact_access", lambda value, *_, **__: value)
    monkeypatch.setattr(talents, "create_talent", lambda *_, **__: pytest.fail("重复请求不能再次保存"))
    result = talents.create_talent_endpoint(ResourcePersonCreate(full_name="人员"), db=db,
                                           idempotency_key="existing-key",
                                           current_user=SimpleNamespace(id=uuid4()))
    assert result.operator_name == "原录入人"
    assert result.operated_at == datetime(2020, 1, 1)
