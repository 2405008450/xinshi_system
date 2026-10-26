"""仅使用内存 SQLite，验证逻辑删除不会破坏历史外键。"""
from uuid import uuid4
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from test_chat_participant_access import environment


def test_user_delete_preserves_history_and_removes_directory_entries(environment, monkeypatch):
    db,(actor,person,other)=environment
    from models import AppUser,EmployeeLeave
    from crud import delete_user,get_users,count_users,update_user
    from schemas import AppUserUpdate
    import organization_service
    monkeypatch.setattr(organization_service,'publish',lambda *args:None)
    # 独立的强约束引用，删除后必须仍可查到原人员。
    db.execute(text('CREATE TABLE deletion_history (id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES app_user(id))'))
    db.execute(text('INSERT INTO deletion_history VALUES (:id,:person)'),{'id':str(uuid4()),'person':person.id.hex});db.commit()
    from business_time import business_now
    leave=EmployeeLeave(id=uuid4(),employee_id=person.id,employee_name=person.full_name,start_date=business_now(),end_date=business_now())
    db.add(leave);db.commit()
    assert delete_user(db,person.id)
    db.refresh(leave)
    assert leave.employee_id==person.id and leave.employee_name==person.full_name
    first_time=person.deleted_at
    assert person.is_deleted is True and person.is_active is False
    assert person.deleted_at.utcoffset().total_seconds()==28800
    assert db.query(AppUser).filter_by(id=person.id).one().full_name==person.full_name
    assert db.execute(text('SELECT employee_id FROM deletion_history')).scalar_one()==person.id.hex
    assert person.id not in {p.id for p in get_users(db)}
    assert count_users(db)==2
    assert update_user(db,person.id,AppUserUpdate(is_active=True)) is None
    assert delete_user(db,person.id) and person.deleted_at==first_time
    assert not delete_user(db,uuid4())


def test_cannot_delete_current_login(monkeypatch):
    from routers import users
    current=SimpleNamespace(id=uuid4())
    with pytest.raises(HTTPException) as error:
        users.delete_user_endpoint(current.id,object(),current)
    assert error.value.status_code==409


def test_deleted_people_excluded_from_department_count_and_roster(environment, monkeypatch):
    db,(actor,person,other)=environment
    from department_models import Department,DepartmentMember
    import department_service,organization_service
    from crud import delete_user
    monkeypatch.setattr(department_service,'can_manage',lambda *args:False)
    monkeypatch.setattr(organization_service,'publish',lambda *args:None)
    dept=Department(id=uuid4(),name='测试部门',aliases=[],revision=1)
    db.add(dept);db.flush()
    person.department=dept.name
    db.add(DepartmentMember(department_id=dept.id,user_id=person.id,position='成员'));db.commit()
    assert next(d for d in department_service.catalog(db,actor)['items'] if d['id']==str(dept.id))['userCount']==1
    delete_user(db,person.id)
    directory=organization_service.directory(db,actor)
    assert str(person.id) not in {p['id'] for p in directory['people']}
    assert next(d for d in directory['items'] if d['id']==str(dept.id))['userCount']==0
