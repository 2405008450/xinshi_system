from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_organization_members import prepare, entry
from routers.departments import PersonDepartmentsWrite


def payload(db, owner, person, service, departments, primary=None):
    data=service.directory(db,owner)
    current=next(row for row in data['people'] if row['id']==str(person.id))
    return PersonDepartmentsWrite(department_ids=[row.id for row in departments],primary_department_id=primary.id if primary else None,
        expected_department_ids=[row['id'] for row in current['departments']],expected_primary_department=current['primaryDepartment'] or None,
        revisions={row['id']:row['revision'] for row in data['items']})


def test_person_department_edit_atomic_and_preserves_position(environment,monkeypatch):
    from department_models import DepartmentMember
    db,owner,member,outsider,a,b,service=prepare(environment,monkeypatch)
    service.save_members(db,owner,b.id,[entry(member,'资源专员')],b.revision)
    request=payload(db,owner,member,service,[a,b],b)
    service.save_person_departments(db,owner,member.id,request)
    assert member.department==b.name
    assert db.get(DepartmentMember,(b.id,member.id)).position=='资源专员'
    assert {row.department_id for row in db.query(DepartmentMember).filter_by(user_id=member.id)}=={a.id,b.id}
    # 清空归属只影响此人，不替换其他人员的名册。
    service.save_members(db,owner,b.id,[entry(member,'资源专员'),entry(outsider)],b.revision)
    service.save_person_departments(db,owner,member.id,payload(db,owner,member,service,[]))
    assert member.department is None
    assert db.query(DepartmentMember).filter_by(user_id=member.id).count()==0
    assert db.get(DepartmentMember,(b.id,outsider.id)) is not None


def test_person_department_permission_and_stale_snapshot(environment,monkeypatch):
    db,owner,member,outsider,a,b,service=prepare(environment,monkeypatch)
    request=payload(db,owner,member,service,[b],b)
    with pytest.raises(HTTPException) as denied:service.save_person_departments(db,outsider,member.id,request)
    assert denied.value.status_code==403
    service.save_members(db,owner,b.id,[entry(member)],b.revision)
    with pytest.raises(HTTPException) as stale:service.save_person_departments(db,owner,member.id,request)
    assert stale.value.status_code==409 and member.department==a.name
    invalid=payload(db,owner,member,service,[a],b)
    with pytest.raises(HTTPException) as error:service.save_person_departments(db,owner,member.id,invalid)
    assert error.value.status_code==422


def test_person_department_alias_is_accepted(environment,monkeypatch):
    db,owner,member,outsider,a,b,service=prepare(environment,monkeypatch)
    a.aliases=['旧客户部'];member.department='旧客户部';db.commit()
    service.save_person_departments(db,owner,member.id,payload(db,owner,member,service,[a,b],a))
    assert member.department==a.name
