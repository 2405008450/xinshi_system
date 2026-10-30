"""入职字段与周年后三个月年假规则；仅隔离 SQLite。"""
from datetime import date
from uuid import uuid4
import pytest
from sqlalchemy import event
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_monthly_shift import setup
from models import AppUser
from schemas import AppUserCreate,AppUserUpdate
import employee_employment as service


@pytest.mark.parametrize('hire,today,expected',[
    (None,'2026-10-28',None),('2026-06-30','2026-10-28',1),('2026-07-01','2026-10-28',0),
    ('2025-06-30','2026-09-29',1),('2025-06-30','2026-09-30',2),
    ('2025-07-01','2026-01-01',1),('2025-07-01','2026-09-30',1),('2025-07-01','2026-10-01',2),
    ('2025-03-31','2026-06-29',1),('2025-03-31','2026-06-30',2),
    ('2024-02-29','2025-05-27',1),('2024-02-29','2025-05-28',2),
    ('2024-11-30','2026-02-27',1),('2024-11-30','2026-02-28',2),
    ('2010-01-01','2026-10-28',10),('2016-07-01','2026-09-30',10),('2016-07-01','2026-10-01',10),
    ('2024-09-09','2024-12-31',0),('2024-09-09','2025-01-01',1),
    ('2024-09-09','2025-12-09',2),('2024-09-09','2026-01-01',2),
    ('2024-09-09','2026-10-30',2),('2025-05-07','2026-10-30',2),('2026-01-12','2026-10-30',1),
    ('2027-01-01','2026-10-28',0)])
def test_cutoff_delay_month_end_leap_and_cap(hire,today,expected):
    assert service.annual_days(date.fromisoformat(hire) if hire else None,date.fromisoformat(today))==expected


def test_next_increase_includes_once_only_january_initial_grant():
    hire=date(2024,9,9)
    assert service.values(hire,date(2024,12,31))['annual_leave_next_increase']==date(2025,1,1)
    assert service.values(hire,date(2025,1,1))['annual_leave_next_increase']==date(2025,12,9)
    assert service.values(hire,date(2026,10,30))['annual_leave_next_increase']==date(2026,12,9)
    assert service.values(date(2016,7,1),date(2026,9,30))['annual_leave_next_increase'] is None


def test_update_clear_omit_and_user_serialization(environment,monkeypatch):
    import crud
    from routers.users import read_user,read_user_page
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    result=crud.update_user(db,person.id,AppUserUpdate(hire_date='2025-06-30'))
    assert result.hire_date==date(2025,6,30)
    from chat_time import api_time
    assert api_time(db.get(service.EmployeeEmployment,person.id).updated_at).utcoffset().total_seconds()==28800
    crud.update_user(db,person.id,AppUserUpdate(full_name='新姓名'))
    assert read_user(person.id,db)['hire_date']==date(2025,6,30)
    page=read_user_page(skip=0,limit=10,include_leave_status=False,db=db)
    assert next(row for row in page['items'] if row['id']==person.id)['hire_date']==date(2025,6,30)
    crud.update_user(db,person.id,AppUserUpdate(hire_date=None))
    assert read_user(person.id,db)['annual_leave_days'] is None


def test_create_user_saves_date_in_same_transaction(environment,monkeypatch):
    import crud,organization_service
    db,users=environment;setup(db,users)
    monkeypatch.setattr(crud,'hash_password',lambda value:'disabled')
    monkeypatch.setattr(organization_service,'publish',lambda *args:None)
    def assign_id(_mapper,_connection,target):
        if target.id is None:target.id=uuid4()
    event.listen(AppUser,'before_insert',assign_id)
    try:
        person=crud.create_user(db,AppUserCreate(username='new-hire',password='test-password',hire_date='2026-07-01'))
        assert person.hire_date==date(2026,7,1)
        assert db.get(service.EmployeeEmployment,person.id).hire_date==date(2026,7,1)
    finally:event.remove(AppUser,'before_insert',assign_id)


def test_private_report_and_company_permissions(environment):
    import crud,attendance_service
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    crud.update_user(db,person.id,AppUserUpdate(hire_date='2025-06-30'))
    report=attendance_service.attendance_report(db,person,date(2026,10,28),'month')
    assert report['annual_leave']['hire_date']==date(2025,6,30) and report['annual_leave']['annual_leave_days']==2
    own=attendance_service.attendance_report(db,other,date(2026,10,28),'month')
    assert own['annual_leave']['hire_date'] is None
    with pytest.raises(HTTPException):attendance_service.attendance_report(db,person,date(2026,10,28),'month',admin=True)


def test_migration_idempotent_does_not_modify_user_table(environment):
    from tools.apply_employee_employment_migration import apply_migration
    from sqlalchemy import inspect
    db,users=environment
    before=[row['name'] for row in inspect(db.connection()).get_columns('app_user')]
    service.EmployeeEmployment.__table__.drop(db.connection());db.commit()
    apply_migration(db.connection());apply_migration(db.connection());db.commit()
    assert [row['name'] for row in inspect(db.connection()).get_columns('app_user')]==before
    assert db.query(AppUser).count()==3 and db.query(service.EmployeeEmployment).count()==0
