from uuid import uuid4
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment  # noqa: F401


def prepare(environment, monkeypatch):
    from department_models import Department
    import organization_service as service
    db, (owner, member, outsider) = environment
    owner.username = 'ethan'
    monkeypatch.setattr('crud.get_user_roles_with_role_names', lambda *a: [])
    monkeypatch.setattr('notification_ws.broadcast_to_users', lambda *a: None)
    a, b = Department(id=uuid4(), name='客户部'), Department(id=uuid4(), name='标注项目部')
    member.department = a.name
    db.add_all([a, b]); db.commit()
    return db, owner, member, outsider, a, b, service


def entry(person, position='项目经理'):
    return SimpleNamespace(user_id=person.id, position=position)


def test_multiple_departments_roster_filter_and_primary_unchanged(environment, monkeypatch):
    from models import AppUser
    db, owner, member, outsider, a, b, service = prepare(environment, monkeypatch)
    data = service.save_members(db, owner, b.id, [entry(member)], b.revision)
    person = next(p for p in data['people'] if p['id'] == str(member.id))
    assert {d['name'] for d in person['departments']} == {'客户部', '标注项目部'}
    assert member.department == '客户部'
    assert db.query(AppUser).filter(service.department_condition(db, ['标注项目部'])).one().id == member.id
    assert next(d for d in data['items'] if d['id'] == str(b.id))['userCount'] == 1
    service.save_members(db, owner, b.id, [], b.revision)
    assert member.department == '客户部'
    assert db.query(AppUser).filter(service.department_condition(db, ['标注项目部'])).count() == 0


def test_permission_concurrency_duplicate_and_primary_removal(environment, monkeypatch):
    db, owner, member, outsider, a, b, service = prepare(environment, monkeypatch)
    with pytest.raises(HTTPException) as denied:
        service.save_members(db, outsider, b.id, [entry(member)], b.revision)
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as duplicate:
        service.save_members(db, owner, b.id, [entry(member), entry(member)], b.revision)
    assert duplicate.value.status_code == 422
    original = b.revision
    service.save_members(db, owner, b.id, [entry(member)], original)
    with pytest.raises(HTTPException) as stale:
        service.save_members(db, owner, b.id, [], original)
    assert stale.value.status_code == 409
    service.save_members(db, owner, a.id, [], a.revision)
    assert member.department == b.name


def test_migration_repeatable_and_primary_edit_preserves_other_departments(environment, monkeypatch):
    from tools.apply_organization_members_migration import apply_migration
    from department_models import DepartmentMember
    db, owner, member, outsider, a, b, service = prepare(environment, monkeypatch)
    apply_migration(db.connection()); db.commit()
    apply_migration(db.connection()); db.commit()
    assert db.query(DepartmentMember).filter_by(user_id=member.id).count() == 1
    service.save_members(db, owner, b.id, [entry(member)], b.revision)
    member.department = None
    service.sync_primary(db, member, a.name); db.commit()
    assert db.query(DepartmentMember).filter_by(user_id=member.id).one().department_id == b.id


def test_membership_aware_default_mentions(environment, monkeypatch):
    from annotation_progress_chat import MentionSelection, resolve_users
    db, owner, member, outsider, a, b, service = prepare(environment, monkeypatch)
    service.save_members(db, owner, b.id, [entry(member)], b.revision)
    assert resolve_users(db, MentionSelection(department_ids=[b.id]), owner) == [member.id]
