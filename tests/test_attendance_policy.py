"""迟到折假、月度档位和可追溯补班/调休；只用隔离 SQLite。"""
from datetime import date
from uuid import uuid4
from types import SimpleNamespace
import pytest
from fastapi import HTTPException,FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,inspect,text
from test_chat_participant_access import environment
from test_monthly_shift import setup,payload,sync
from test_attendance import at
from attendance_models import AttendanceClockSession as Clock,AttendanceLeave,AttendanceCompTimeRequest
from employee_employment import EmployeeEmployment
import attendance_policy as policy
import attendance_comp_time as comp
import attendance_service as attendance


@pytest.mark.parametrize('minutes,free',[(0,1),(599.99,1),(600,1),(600.01,3),(1200,3),(1200.01,5)])
def test_exact_overtime_boundaries(minutes,free):assert policy.free_late_count(minutes)==free


def punch(user,day,start='09:30',end='18:30',**flags):
    return Clock(id=uuid4(),user_id=user.id,day=date.fromisoformat(day),segment=0,check_in=at(f'{day}T{start}'),check_out=at(f'{day}T{end}') if end else None,shift_snapshot={'code':'early','label':'早班','periods':['09:00–12:00','13:30–18:30'],**flags},confirmations={'breakfast_after_eating':True,'early_work_confirmed':True})


def test_late_spans_exclude_formal_leave_rest_and_grace():
    import main  # 注册既有 ORM 关联；不运行 startup。
    user=SimpleNamespace(id=uuid4());row=punch(user,'2026-10-26','14:00')
    leave=SimpleNamespace(employee_id=user.id,start_date=at('2026-10-26T09:00'),end_date=at('2026-10-26T10:00'))
    event=policy.lateness_events([row],[leave])[0]
    assert event['minutes']==135
    assert [(item['start_at'].strftime('%H:%M'),item['end_at'].strftime('%H:%M')) for item in event['spans']]==[('10:15','12:00'),('13:30','14:00')]
    assert event['clock_id']==str(row.id)


def test_report_adds_virtual_leave_with_original_clock_reference_and_full_month_threshold(environment,monkeypatch):
    db,users=environment;setup(db,users);admin,person,other=users
    a=punch(person,'2026-10-05');b=punch(person,'2026-10-26');overtime=punch(person,'2026-10-06','09:00','23:00')
    # 第二个加班日使整月跨过10小时，周视图不能仅按当周加班判断。
    c=punch(person,'2026-10-07','09:00','23:00');d=punch(person,'2026-10-08','09:00','23:00')
    db.add_all([a,b,overtime,c,d]);db.commit()
    report=attendance.attendance_report(db,person,date(2026,10,26),'week')
    assert report['totals']['leave_minutes']==15 and report['totals']['late_leave_minutes']==15
    assert report['totals']['requested_leave_minutes']==0
    assert len(report['leaves'])==1 and report['leaves'][0]['source']=='lateness'
    assert report['leaves'][0]['clock_id']==str(b.id)
    assert report['monthly_policy'][0]['late_count']==2 and report['monthly_policy'][0]['free_count']==3
    assert report['records'][0]['late_leave_events'][0]['ordinal']==2
    assert db.query(AttendanceLeave).count()==0
    assert attendance.attendance_report(db,other,date(2026,10,26),'month')['leaves']==[]


def test_first_allowed_occurrences_and_linked_sources_recompute_with_overtime():
    uid=uuid4();events=[{'user_id':str(uid),'month':'2026-10','id':str(i),'minutes':10} for i in range(6)]
    def compute(minutes):return policy.accountability(events,[{'user_id':str(uid),'month':'2026-10','overtime_minutes':minutes}],[uid],date(2026,10,1),date(2026,10,31))[0]
    assert compute(600)['linked_count']==5
    assert [row['ordinal'] for row in compute(900)['events'] if row['bonus_linked']]==[4,5,6]
    assert [row['ordinal'] for row in compute(1201)['events'] if row['bonus_linked']]==[6]
    assert compute(1201)['late_leave_minutes']==60


def duty(day,minutes=480):return {'id':f'duty:{day}','day':day,'minutes':minutes}


@pytest.mark.parametrize('hire,exempt,months',[(date(2026,10,16),None,1),(date(2026,10,17),'2026-10',0),(date(2026,9,16),'2026-09',1),(date(2026,9,15),None,2)])
def test_inclusive_fifteen_day_first_month_rule(hire,exempt,months):
    result=comp.allocation([],[],[],hire,date(2026,10,29))
    assert result['exempt_month']==exempt and result['counted_months']==months


def test_makeup_fifo_before_comp_time_reservation_no_double_use():
    duties=[duty('2026-10-11'),duty('2026-10-17'),duty('2026-10-18')]
    leaves=[{'id':'leave:1','day':'2026-10-12','minutes':90,'source':'application'},{'id':'late:1','day':'2026-10-13','minutes':30,'source':'lateness'}]
    requests=[{'id':'request:1','created_at':'2026-10-20','minutes':120}]
    value=comp.allocation(duties,leaves,requests,date(2026,10,1),date(2026,10,29))
    assert value['eligible'] and value['extra_minutes']==960 and value['available_minutes']==720
    assert value['obligations'][0]['makeup_links'][0]['duty_id']=='duty:2026-10-17'
    assert sum(item['minutes'] for row in value['duties'] for item in row['uses'])==240
    assert all(row['remaining_minutes']==0 for row in value['obligations'])
    # 恰好平均每月1天不可申请，即使某个月多另一个月少。
    value=comp.allocation(duties[:2],[],[],date(2026,9,1),date(2026,10,29))
    assert value['average_days']==1 and not value['eligible'] and value['available_minutes']==0
    # 两个月只在一个月值班3天，须补足另一个月的1天基数后仅余1天。
    value=comp.allocation(duties,[],[],date(2026,9,1),date(2026,10,29))
    assert value['available_minutes']==480 and value['eligible']
    assert value['duties'][1]['uses'][0]['kind']=='baseline'
    assert not comp.allocation(duties,[],[],None,date(2026,10,29))['eligible']


def test_actual_completed_weekend_duty_excludes_holidays_workdays_unfinished_and_home_overtime(environment,monkeypatch):
    db,users=environment;setup(db,users);person=users[1]
    db.add(EmployeeEmployment(user_id=person.id,hire_date=date(2026,10,1)))
    db.add_all([punch(person,'2026-10-11','09:00',weekend_duty=True),punch(person,'2026-10-17','09:00',weekend_duty=True,home_office_day=True),punch(person,'2026-10-18','09:00',end=None,weekend_duty=True),punch(person,'2026-10-10','09:00',weekend_duty=True),punch(person,'2026-10-04','09:00',weekend_duty=True),punch(person,'2026-10-24','09:00',weekend_duty=True,overtime_only=True)])
    db.commit();value=comp.balances(db,[person],date(2026,10,29))[0]
    assert value['duty_days']==2 and value['available_minutes']==480
    assert value['duties'][1]['home']


def test_comp_request_reserves_once_with_server_checks_and_private_scope(environment,monkeypatch):
    db,users=environment;setup(db,users);admin,person,other=users
    monkeypatch.setattr(comp,'now',lambda:at('2026-10-29T10:00'))
    db.add(EmployeeEmployment(user_id=person.id,hire_date=date(2026,10,1)))
    db.add_all([punch(person,'2026-10-11','09:00',weekend_duty=True),punch(person,'2026-10-17','09:00',weekend_duty=True)]);db.commit()
    import weekly_shift
    weekly_shift.save_plan(db,admin,'2026-10-26',weekly_shift.WeeklyPlanWrite(revision=0,assignments=payload(person).assignments));sync(db,admin,'2026-10-26')
    request=attendance.LeaveWrite(client_id=uuid4(),start_at=at('2026-10-30T09:00'),end_at=at('2026-10-30T11:00'),reason='调休隔离测试')
    value=comp.submit(db,person,request)
    assert comp.submit(db,person,request)['record']['id']==value['record']['id']
    assert db.query(AttendanceCompTimeRequest).count()==1 and db.query(AttendanceLeave).count()==0
    assert comp.balances(db,[person],date(2026,10,29))[0]['available_minutes']==360
    with pytest.raises(HTTPException) as overlap_error:attendance.create_leave(db,person,request.model_copy(update={'client_id':uuid4()}))
    assert overlap_error.value.status_code==409 and '调休' in overlap_error.value.detail
    with pytest.raises(HTTPException):comp.submit(db,other,request)
    with pytest.raises(HTTPException):comp.submit(db,person,request.model_copy(update={'client_id':uuid4()}))
    with pytest.raises(HTTPException):comp.submit(db,person,request.model_copy(update={'client_id':uuid4(),'start_at':at('2026-10-30T10:00'),'end_at':at('2026-10-30T18:30')}))
    with pytest.raises(HTTPException):comp.overview(db,person,2026,admin=True)
    mine=comp.overview(db,other,2026)
    assert [row['user_id'] for row in mine['balances']]==[str(other.id)] and not mine['balances'][0]['requests']
    row=db.query(AttendanceCompTimeRequest).one()
    assert row.allocation_snapshot['balance']['hire_date']=='2026-10-01'
    with pytest.raises(HTTPException):comp.cancel(db,other,row.id)
    assert comp.cancel(db,person,row.id)['status']=='cancelled'
    assert comp.cancel(db,person,row.id)['status']=='cancelled'
    assert comp.balances(db,[person],date(2026,10,29))[0]['available_minutes']==480


def test_mobile_comp_request_rejected_and_company_requires_hr(environment):
    from routers.attendance import router
    from routers.auth import get_current_user
    from database import get_db
    db,users=environment;setup(db,users);person=users[1]
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:person
    with TestClient(app) as client:
        value=client.post('/attendance/comp-time',headers={'user-agent':'iPhone Mobile'},json={'client_id':str(uuid4()),'start_at':'2026-10-30T09:00+08:00','end_at':'2026-10-30T10:00+08:00','reason':'测试'})
        assert value.status_code==403
        assert client.get('/attendance/policy/company?year=2026').status_code==403
        assert client.get('/attendance/policy?year=2026').status_code==200


def test_migration_idempotent_no_existing_table_alter():
    from tools.apply_attendance_comp_time_migration import apply_migration
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE app_user (id UUID PRIMARY KEY)'))
        apply_migration(connection);apply_migration(connection)
        assert inspect(connection).has_table('attendance_comp_time_request')
        assert [row['name'] for row in inspect(connection).get_columns('app_user')]==['id']
    engine.dispose()
