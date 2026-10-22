from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_chat_participant_access import environment  # noqa: F401


def prepare(environment,monkeypatch):
    db,users=environment
    import department_service as service
    monkeypatch.setattr('crud.get_user_roles_with_role_names',lambda db,uid: [])
    monkeypatch.setattr('notification_ws.broadcast_to_users',lambda *args:None)
    return db,users,service


def test_management_is_exact_username_or_super_role(environment,monkeypatch):
    db,(owner,member,outsider),service=prepare(environment,monkeypatch)
    owner.username='Ethan';member.username='jimmy';outsider.full_name='ethan'
    assert service.can_manage(db,owner) and service.can_manage(db,member)
    assert not service.can_manage(db,outsider)
    with pytest.raises(HTTPException) as denied:service.save(db,outsider,'部门X')
    assert denied.value.status_code==403
    monkeypatch.setattr('crud.get_user_roles_with_role_names',lambda db,uid:['超级管理员'])
    assert service.can_manage(db,outsider)
    outsider.is_active=False
    assert not service.can_manage(db,outsider)


def test_rename_syncs_users_schedule_and_aliases_but_preserves_free_text(environment,monkeypatch):
    from models import WorkSchedule
    from department_models import Department
    from department_utils import department_filter_values
    db,(owner,member,outsider),service=prepare(environment,monkeypatch)
    owner.username='ethan';member.department='IT部';outsider.department='翻译部'
    row=Department(name='IT部',aliases=['翻译部']);db.add(row)
    schedule=WorkSchedule(id=uuid4(),schedule_date=date(2026,10,22),dept_person_data=[{'dept':'IT部','tasks':[{'department':'翻译部','name':'IT部'}]}],not_scheduled_tasks=[{'department':'翻译部','remarks':'IT部'}])
    db.add(schedule);db.commit()
    service.save(db,owner,'技术部',row.id,row.revision)
    db.expire_all()
    assert member.department==outsider.department=='技术部'
    assert schedule.dept_person_data==[{'dept':'技术部','tasks':[{'department':'技术部','name':'IT部'}]}]
    assert schedule.not_scheduled_tasks[0]=={'department':'技术部','remarks':'IT部'}
    assert schedule.updated_by==owner.id and schedule.updated_at is not None
    assert service.canonical_name(db,'翻译部')=='技术部'
    assert set(department_filter_values('IT部',db))=={'技术部','IT部','翻译部'}
    assert service.catalog(db,owner)['items'][0]['userCount']==2
    with pytest.raises(HTTPException) as duplicate:service.save(db,owner,'IT部')
    assert duplicate.value.status_code==409
    with pytest.raises(HTTPException) as stale:service.save(db,owner,'技术一部',row.id,1)
    assert stale.value.status_code==409


def test_initialization_preserves_existing_departments_and_is_repeatable(environment,monkeypatch):
    from department_models import Department
    from tools.apply_department_catalog_migration import apply_migration
    db,(owner,member,outsider),service=prepare(environment,monkeypatch)
    owner.department='自定义运营组';owner.username='jimmy';db.commit()
    apply_migration(db.connection());db.commit()
    first=db.query(Department).count()
    assert db.query(Department).filter_by(name='自定义运营组').one()
    row=db.query(Department).filter_by(name='IT部').one()
    service.save(db,owner,'研发部',row.id,row.revision)
    apply_migration(db.connection());db.commit()
    assert db.query(Department).count()==first
    assert not db.query(Department).filter_by(name='IT部').first()


def test_department_name_validation():
    from routers.departments import DepartmentWrite
    assert DepartmentWrite(name=' 部门A ').name=='部门A'
    for name in ['   ','a'*51]:
        with pytest.raises(ValidationError):DepartmentWrite(name=name)


def test_directory_must_be_initialized_and_user_edit_cannot_create_unknown_department(environment,monkeypatch):
    from department_models import Department
    db,(owner,member,outsider),service=prepare(environment,monkeypatch)
    owner.username='ethan'
    with pytest.raises(HTTPException) as invalid:service.canonical_name(db,'未经授权的新部门')
    assert invalid.value.status_code==422
    Department.__table__.drop(db.connection());db.commit()
    assert not service.catalog(db,owner)['ready']
    with pytest.raises(HTTPException) as unavailable:service.save(db,owner,'部门X')
    assert unavailable.value.status_code==503
