"""周末值班日期、重复安排、权限和并发；仅使用隔离 SQLite。"""
from datetime import date
from uuid import uuid4
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect
from test_chat_participant_access import environment
from test_monthly_shift import setup
import weekend_duty as service


def payload(person,revision=0,dates=('2026-11-01',)):
    return service.DutyWrite(revision=revision,assignments=[{'user_id':person.id,'department':'customer','date':day} for day in dates])


def test_weekends_month_boundaries_and_permission(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    days=service.weekend_dates(date(2026,11,1))
    assert [day.day for day in days]==[1,7,8,14,15,21,22,28,29]
    assert all(day.month==11 and day.weekday()>=5 for day in days)
    assert len(service.weekend_dates(date(2026,2,1)))==8
    for user in [person,other]:
        with pytest.raises(HTTPException) as error:service.get_plan(db,user,'2026-11')
        assert error.value.status_code==403
        with pytest.raises(HTTPException):service.save_plan(db,user,'2026-11',payload(user))


def test_repeated_person_on_distinct_days_move_return_and_month_isolation(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    saved=service.save_plan(db,admin,'2026-11',payload(person,dates=('2026-11-01','2026-11-07')))
    assert saved['revision']==1 and len(saved['assignments'])==2
    assert [row['user_id'] for row in saved['assignments']]==[str(person.id)]*2
    assert saved['updated_at'].utcoffset().total_seconds()==28800
    assert service.get_plan(db,admin,'2026-10')['assignments']==[]
    with pytest.raises(HTTPException) as error:service.save_plan(db,admin,'2026-11',payload(person))
    assert error.value.status_code==409
    saved=service.save_plan(db,admin,'2026-11',payload(person,revision=1,dates=('2026-11-01','2026-11-08')))
    assert [row['date'] for row in saved['assignments']]==['2026-11-01','2026-11-08']
    saved=service.save_plan(db,admin,'2026-11',payload(person,revision=2))
    assert len(saved['assignments'])==1 and saved['assignments'][0]['date']=='2026-11-01'
    assert service.get_plan(db,admin,'2026-11')['assignments']==saved['assignments']


def test_invalid_duplicate_and_nonparticipating_people(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    with pytest.raises(ValidationError):payload(person,dates=('2026-11-01','2026-11-01'))
    with pytest.raises(ValidationError):payload(person,dates=('2026-11-02',))
    with pytest.raises(HTTPException) as error:service.save_plan(db,admin,'2026-11',payload(person,dates=('2026-10-31',)))
    assert error.value.status_code==422
    unknown=service.DutyWrite(revision=0,assignments=[{'user_id':uuid4(),'department':'customer','date':'2026-11-01'}])
    with pytest.raises(HTTPException):service.save_plan(db,admin,'2026-11',unknown)
    person.is_active=False;db.commit()
    with pytest.raises(HTTPException):service.save_plan(db,admin,'2026-11',payload(person))


def test_create_table_idempotent_and_existing_records_unchanged(environment):
    from tools.apply_weekend_duty_migration import apply_migration
    from monthly_shift import MonthlyShiftPlan
    import monthly_shift
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    monthly_shift.save_plan(db,admin,'2026-11',monthly_shift.PlanWrite(revision=0,assignments=[{'user_id':person.id,'department':'customer','shift':'early'}]))
    before=db.get(MonthlyShiftPlan,date(2026,11,1)).assignments
    service.WeekendDutyPlan.__table__.drop(db.connection());db.commit()
    assert not service.ready(db)
    apply_migration(db.connection());apply_migration(db.connection());db.commit()
    assert inspect(db.connection()).has_table('weekend_duty_plan')
    assert db.get(MonthlyShiftPlan,date(2026,11,1)).assignments==before


def test_api_scope_and_optimistic_lock(environment):
    from routers.monthly_shifts import router
    from routers.auth import get_current_user
    from database import get_db
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:person
    with TestClient(app) as client:
        assert client.get('/monthly-shifts/weekend-duty?month=2026-11').status_code==403
        assert client.put('/monthly-shifts/weekend-duty?month=2026-11',json=payload(person).model_dump(mode='json')).status_code==403
        app.dependency_overrides[get_current_user]=lambda:admin
        assert client.put('/monthly-shifts/weekend-duty?month=2026-11',json=payload(person).model_dump(mode='json')).status_code==200
        assert client.put('/monthly-shifts/weekend-duty?month=2026-11',json=payload(person).model_dump(mode='json')).status_code==409
