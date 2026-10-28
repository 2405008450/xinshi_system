"""每周独立排班、月度历史隔离、跨月跨年、权限与本人只读。仅隔离 SQLite。"""
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_chat_participant_access import environment
from test_monthly_shift import setup
import weekly_shift as service
import monthly_shift as monthly

def payload(person,revision=0,shift='early'):
    return service.WeeklyPlanWrite(revision=revision,assignments=[{'user_id':person.id,'department':'customer','shift':shift}])

@pytest.mark.parametrize('value,expected',[('2026-10-25','2026-10-19'),('2026-10-26','2026-10-26'),('2026-11-01','2026-10-26'),('2027-01-01','2026-12-28')])
def test_week_boundary(value,expected):assert service.week_key(value).isoformat()==expected

def test_weekly_independent_monthly_unchanged_and_conflict(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    monthly.save_plan(db,admin,'2026-10',monthly.PlanWrite(revision=0,assignments=payload(person).assignments))
    first=service.save_plan(db,admin,'2026-10-19',payload(person))
    second=service.save_plan(db,admin,'2026-10-26',payload(person,shift='late'))
    assert first['week_end']=='2026-10-25' and second['week_end']=='2026-11-01'
    assert service.get_plan(db,admin,'2026-10-25')['assignments'][0]['shift']=='early'
    assert service.get_plan(db,admin,'2026-11-01')['assignments'][0]['shift']=='late'
    assert monthly.get_plan(db,admin,'2026-10')['assignments'][0]['shift']=='early'
    with pytest.raises(HTTPException) as error:service.save_plan(db,admin,'2026-10-26',payload(person))
    assert error.value.status_code==409
    service.save_plan(db,admin,'2026-10-26',service.WeeklyPlanWrite(revision=second['revision'],assignments=[]))
    assert service.get_plan(db,admin,'2026-10-26')['assignments']==[]
    assert len(service.get_plan(db,admin,'2026-10-19')['assignments'])==1
    assert first['updated_at'].utcoffset().total_seconds()==28800

def test_permissions_personal_privacy_and_validation(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    with pytest.raises(HTTPException):service.get_plan(db,person,'2026-10-19')
    with pytest.raises(HTTPException):service.save_plan(db,other,'2026-10-19',payload(person))
    with pytest.raises(ValidationError,match='每周'):service.WeeklyPlanWrite(revision=0,assignments=payload(person).assignments*2)
    for value in ['2026-13-01','2026-1-1','bad']:
        with pytest.raises(HTTPException):service.week_key(value)
    service.save_plan(db,admin,'2026-10-19',payload(person))
    mine=service.my_plan(db,person,'2026-10-25');assert mine['assignment']['user_id']==str(person.id)
    assert 'assignments' not in mine and service.my_plan(db,other,'2026-10-25')['assignment'] is None
    assert service.my_plan(db,person,'2026-10-26')['assignment'] is None

def test_migration_idempotent(environment):
    from tools.apply_weekly_shift_migration import apply_migration
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    monthly.save_plan(db,admin,'2026-10',monthly.PlanWrite(revision=0,assignments=payload(person).assignments))
    service.WeeklyShiftPlan.__table__.drop(db.connection());db.commit()
    assert not service.ready(db)
    apply_migration(db.connection());apply_migration(db.connection());db.commit()
    assert service.ready(db) and len(monthly.get_plan(db,admin,'2026-10')['assignments'])==1

def test_weekly_api_and_personal_endpoint_cannot_select_another_user(environment):
    from routers.monthly_shifts import router
    from routers.auth import get_current_user
    from database import get_db
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    service.save_plan(db,admin,'2026-10-19',payload(person))
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:other
    with TestClient(app) as client:
        assert client.get('/monthly-shifts/weekly?week=2026-10-19').status_code==403
        assert client.put('/monthly-shifts/weekly?week=2026-10-19',json=payload(person).model_dump(mode='json')).status_code==403
        assert client.get(f'/monthly-shifts/weekly/mine?week=2026-10-19&user_id={person.id}').json()['assignment'] is None


def transfer(source,target,source_revision,target_revision,operation='move'):
    return service.WeekTransfer(source_week=source,target_week=target,source_revision=source_revision,target_revision=target_revision,operation=operation)


def test_transfer_move_replace_and_swap_are_atomic_and_revision_protected(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    service.save_plan(db,admin,'2026-10-19',payload(person))
    service.save_plan(db,admin,'2026-10-26',payload(other,shift='late'))
    result=service.transfer_plan(db,admin,transfer('2026-10-19','2026-10-26',1,1,'swap'))
    assert result['source']['assignments'][0]['user_id']==str(other.id)
    assert result['target']['assignments'][0]['user_id']==str(person.id)
    with pytest.raises(HTTPException) as error:service.transfer_plan(db,admin,transfer('2026-10-19','2026-10-26',1,2))
    assert error.value.status_code==409
    assert service.get_plan(db,admin,'2026-10-26')['revision']==2
    result=service.transfer_plan(db,admin,transfer('2026-10-26','2026-10-19',2,2))
    assert result['source']['assignments']==[]
    assert result['target']['assignments'][0]['user_id']==str(person.id)
    result=service.transfer_plan(db,admin,transfer('2026-10-19','2026-12-28',3,0))
    assert result['target']['week_end']=='2027-01-03'
    assert result['target']['revision']==1 and result['source']['assignments']==[]


def test_transfer_fixed_people_permissions_and_empty_weeks(environment):
    import fixed_shift
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    service.save_plan(db,admin,'2026-12-21',service.WeeklyPlanWrite(revision=0,assignments=[*payload(person).assignments,*payload(other).assignments]))
    fixed_shift.save_config(db,admin,monthly.PlanWrite(revision=0,assignments=payload(other,shift='late').assignments))
    result=service.transfer_plan(db,admin,transfer('2026-12-21','2026-12-28',1,0))
    assert [row['user_id'] for row in result['source']['assignments']]==[str(other.id)]
    assert next(row for row in result['target']['assignments'] if row['user_id']==str(other.id))['fixed']
    assert next(row for row in result['target']['assignments'] if row['user_id']==str(person.id))['shift']=='early'
    with pytest.raises(HTTPException) as error:service.transfer_plan(db,person,transfer('2026-12-21','2026-12-28',2,1))
    assert error.value.status_code==403
    for request in [transfer('2026-12-21','2026-12-25',2,2),transfer('2026-12-21','2027-01-04',2,0)]:
        with pytest.raises(HTTPException) as error:service.transfer_plan(db,admin,request)
        assert error.value.status_code==422


def test_transfer_endpoint_rejects_old_preview(environment):
    from routers.monthly_shifts import router
    from routers.auth import get_current_user
    from database import get_db
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    service.save_plan(db,admin,'2026-10-19',payload(person))
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:admin
    with TestClient(app) as client:
        data=transfer('2026-10-19','2026-10-26',0,0).model_dump()
        assert client.post('/monthly-shifts/weekly/transfer',json=data).status_code==409
        data['source_revision']=1
        assert client.post('/monthly-shifts/weekly/transfer',json=data).status_code==200


def test_copy_keeps_source_revision_and_replaces_only_target(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    service.save_plan(db,admin,'2026-10-26',payload(person))
    service.save_plan(db,admin,'2026-11-02',payload(other,shift='late'))
    before=service.get_plan(db,admin,'2026-10-26')
    result=service.transfer_plan(db,admin,transfer('2026-10-26','2026-11-02',1,1,'copy'))
    assert result['source']==before
    assert result['target']['revision']==2
    assert result['target']['assignments'][0]['user_id']==str(person.id)
    result=service.transfer_plan(db,admin,transfer('2026-10-26','2026-12-28',1,0,'copy'))
    assert result['source']==before and result['target']['revision']==1
    with pytest.raises(HTTPException) as error:service.transfer_plan(db,admin,transfer('2026-10-26','2026-11-02',1,1,'copy'))
    assert error.value.status_code==409
    with pytest.raises(HTTPException) as error:service.transfer_plan(db,admin,transfer('2026-11-09','2026-11-02',0,2,'copy'))
    assert error.value.status_code==422
    assert service.get_plan(db,admin,'2026-11-02')['revision']==2


def test_copy_does_not_propagate_fixed_assignments(environment):
    import fixed_shift
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    fixed_shift.save_config(db,admin,monthly.PlanWrite(revision=0,assignments=payload(other,shift='late').assignments))
    service.save_plan(db,admin,'2026-12-21',payload(person))
    service.transfer_plan(db,admin,transfer('2026-12-21','2026-12-28',1,0,'copy'))
    from datetime import date
    raw=db.get(service.WeeklyShiftPlan,date(2026,12,28))
    assert [entry['user_id'] for entry in raw.assignments]==[str(person.id)]
    effective=service.overview(db,person,'2026-12-28')['assignments']
    assert next(row for row in effective if row['user_id']==str(other.id))['fixed']


def test_workbench_overview_all_users_readonly_without_hr_access(environment):
    from routers.monthly_shifts import router
    from routers.auth import get_current_user
    from database import get_db
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    service.save_plan(db,admin,'2026-10-26',service.WeeklyPlanWrite(revision=0,assignments=[*payload(person).assignments,*payload(other).assignments]))
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:person
    with TestClient(app) as client:
        response=client.get('/monthly-shifts/weekly/overview?week=2026-11-01')
        assert response.status_code==200
        assert {row['user_id'] for row in response.json()['assignments']}=={str(person.id),str(other.id)}
        assert all('leaves' not in row and 'leave_minutes' not in row for row in response.json()['assignments'])
        assert client.get('/monthly-shifts/weekly?week=2026-10-26').status_code==403
        assert client.put('/monthly-shifts/weekly?week=2026-10-26',json=payload(person,1).model_dump(mode='json')).status_code==403
        assert client.post('/monthly-shifts/weekly/transfer',json=transfer('2026-10-26','2026-11-02',1,0,'copy').model_dump()).status_code==403
        person.is_active=False;db.commit()
        assert client.get('/monthly-shifts/weekly/overview?week=2026-10-26').status_code==403
