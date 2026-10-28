"""手动打卡、确认、分段、月抵扣与权限；仅隔离 SQLite。"""
from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException,FastAPI
from fastapi.testclient import TestClient
from test_chat_participant_access import environment
from test_monthly_shift import setup,payload,sync
from test_attendance import at,request
from attendance_models import AttendanceClockSession as Clock,AttendanceDay
import attendance_clock as service
import attendance_service as attendance
import weekly_shift


def arrange(db,users,shift='early',fixed=False):
    setup(db,users)
    weekly_shift.save_plan(db,users[0],'2026-10-26',weekly_shift.WeeklyPlanWrite(revision=0,assignments=payload(users[1],shift=shift).assignments))
    sync(db,users[0],'2026-10-26')
    if fixed:
        from weekly_shift_publication import WeeklyShiftPublication
        row=db.get(WeeklyShiftPublication,date(2026,10,26));row.assignments=[{**entry,'fixed':True} for entry in row.assignments];db.commit()


def punch(db,user,monkeypatch,moment,segment=0):
    monkeypatch.setattr(service,'now',lambda:at(moment))
    return service.check_in(db,user,request(),service.CheckInWrite(segment=segment,breakfast_notice_accepted=True))['record']


def out(db,user,record,monkeypatch,moment,**values):
    monkeypatch.setattr(service,'now',lambda:at(moment))
    return service.check_out(db,user,request(),service.CheckOutWrite(record_id=record['id'],early_work_confirmed=values.pop('early_work_confirmed',True),breakfast_after_eating=values.pop('breakfast_after_eating',True),**values))['record']


@pytest.mark.parametrize('worked,expected',[(True,60),(False,0)])
def test_manual_breakfast_notice_early_confirmation_and_idempotence(environment,monkeypatch,worked,expected):
    db,users=environment;arrange(db,users);admin,person,other=users
    assert attendance.auto_check_in(db,person,request())['status']=='manual_required'
    assert db.query(Clock).count()==0 and db.query(AttendanceDay).count()==0
    with pytest.raises(HTTPException):service.check_in(db,person,request(),service.CheckInWrite(breakfast_notice_accepted=False))
    record=punch(db,person,monkeypatch,'2026-10-26T08:00')
    repeated=punch(db,person,monkeypatch,'2026-10-26T08:15');assert repeated['check_in']==record['check_in']
    record=out(db,person,record,monkeypatch,'2026-10-26T18:30',early_work_confirmed=worked)
    assert record['early_minutes']==60 and record['overtime_minutes']==expected
    assert out(db,person,record,monkeypatch,'2026-10-26T19:00',early_work_confirmed=not worked)['check_out']==record['check_out']
    with pytest.raises(HTTPException):out(db,other,record,monkeypatch,'2026-10-26T19:00')


def test_fixed_dinner_breakfast_violation_and_monthly_offset(environment,monkeypatch):
    db,users=environment;arrange(db,users,fixed=True);admin,person,other=users
    first=punch(db,person,monkeypatch,'2026-10-26T08:00')
    first=out(db,person,first,monkeypatch,'2026-10-26T18:30',breakfast_after_eating=False)
    assert first['raw_overtime_minutes']==60 and first['breakfast_deduction_minutes']==15 and first['dinner_deduction_minutes']==20
    assert first['overtime_minutes']==25 and first['violation_count']==1
    second=punch(db,person,monkeypatch,'2026-10-27T09:00');second=out(db,person,second,monkeypatch,'2026-10-27T18:30')
    assert second['overtime_minutes']==-20
    report=attendance.attendance_report(db,person,date(2026,10,26),'month')
    assert report['totals']['overtime_minutes']==5 and report['totals']['violation_count']==1
    balance=report['monthly_balances'][0];assert balance['raw_minutes']==60 and balance['deduction_minutes']==55 and balance['overtime_minutes']==5
    assert {row['user_id'] for row in report['records']}=={str(person.id)}
    assert attendance.attendance_report(db,other,date(2026,10,26),'month')['records']==[]
    with pytest.raises(HTTPException):attendance.attendance_report(db,person,date(2026,10,26),'month',admin=True)


@pytest.mark.parametrize('code,eaten,expected',[('late',True,-20),('late',False,0),('late_late',True,-20),('late_late',False,0)])
def test_late_dinner_choice(environment,monkeypatch,code,eaten,expected):
    db,users=environment;arrange(db,users,code);person=users[1]
    start,end=('10:30','20:00') if code=='late' else ('13:30','21:30')
    record=punch(db,person,monkeypatch,'2026-10-26T'+start)
    with pytest.raises(HTTPException):out(db,person,record,monkeypatch,'2026-10-26T'+end)
    record=out(db,person,record,monkeypatch,'2026-10-26T'+end,dinner_eaten=eaten)
    assert record['overtime_minutes']==expected


def test_remote_two_segments_no_dinner_and_invalid_deduction(environment,monkeypatch):
    db,users=environment;arrange(db,users,'customer_remote',True);person=users[1]
    first=punch(db,person,monkeypatch,'2026-10-26T10:00')
    with pytest.raises(HTTPException):punch(db,person,monkeypatch,'2026-10-26T17:00',1)
    first=out(db,person,first,monkeypatch,'2026-10-26T18:00',deduct_invalid_time=True,invalid_minutes=10,invalid_reason='个人事务')
    assert first['dinner_deduction_minutes']==0 and first['overtime_minutes']==20
    second=punch(db,person,monkeypatch,'2026-10-26T20:30',1)
    with pytest.raises(HTTPException):out(db,person,second,monkeypatch,'2026-10-26T23:30',deduct_invalid_time=False,dinner_eaten=True)
    second=out(db,person,second,monkeypatch,'2026-10-26T23:30',deduct_invalid_time=False)
    assert second['overtime_minutes']==60 and second['dinner_deduction_minutes']==0
    report=attendance.attendance_report(db,person,date(2026,10,26),'month')
    assert len(report['records'])==1 and len(report['records'][0]['sessions'])==2
    assert report['totals']['overtime_minutes']==80
    monkeypatch.setattr(service,'now',lambda:at('2026-10-26T23:40'))
    assert service.today_status(db,person)['can_check_in'] is False


def test_api_confirmation_required_mobile_denied_and_no_other_user_scope(environment,monkeypatch):
    from routers.attendance import router
    from routers.auth import get_current_user
    from database import get_db
    db,users=environment;arrange(db,users);person=users[1]
    monkeypatch.setattr(service,'now',lambda:at('2026-10-26T08:00'))
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:person
    headers={'user-agent':'Mozilla Windows NT','x-client-type':'desktop'}
    with TestClient(app) as client:
        assert client.post('/attendance/check-in',json={'breakfast_notice_accepted':True},headers={'user-agent':'iPhone Mobile'}).status_code==403
        record=client.post('/attendance/check-in',json={'breakfast_notice_accepted':True},headers=headers).json()['record']
        assert client.post('/attendance/check-out',json={'record_id':record['id']},headers=headers).status_code==422
        assert client.get('/attendance/mine?anchor=2026-10-26&period=month&user_id='+str(users[0].id)).json()['records'][0]['user_id']==str(person.id)


def test_migration_idempotent_old_rows_unchanged(environment):
    from tools.apply_attendance_clock_migration import apply_migration
    db,users=environment;arrange(db,users)
    old=AttendanceDay(user_id=users[1].id,day=date(2026,10,25),check_in=at('2026-10-25T09:00'),shift_snapshot={'code':'early','periods':['09:00–18:30']});db.add(old);db.commit()
    Clock.__table__.drop(db.connection());db.commit();apply_migration(db.connection());apply_migration(db.connection());db.commit()
    assert db.query(AttendanceDay).one().check_in.hour==9 and db.query(Clock).count()==0


def completed(db,user,day,start,end,fixed=False):
    from monthly_shift import SHIFTS
    db.add(Clock(user_id=user.id,day=date.fromisoformat(day),segment=0,check_in=at(day+'T'+start),check_out=at(day+'T'+end),shift_snapshot=service.snapshot({**SHIFTS[1],'fixed':fixed},0),confirmations={'early_work_confirmed':True,'breakfast_after_eating':True}));db.commit()


def test_company_never_offsets_one_person_against_another(environment):
    db,users=environment;arrange(db,users)
    completed(db,users[1],'2026-10-26','09:00','18:30',True)
    completed(db,users[2],'2026-10-26','09:00','19:30')
    company=attendance.attendance_report(db,users[0],date(2026,10,26),'month',admin=True)
    assert company['totals']['overtime_minutes']==60
    assert next(row for row in company['monthly_balances'] if row['user_id']==str(users[1].id))['remaining_deduction_minutes']==20


def test_week_spanning_months_never_transfers_deductions_between_months(environment):
    db,users=environment;arrange(db,users)
    completed(db,users[1],'2026-10-30','09:00','19:30')
    completed(db,users[1],'2026-11-01','09:00','18:30',True)
    report=attendance.attendance_report(db,users[1],date(2026,10,26),'week')
    assert report['totals']['overtime_minutes']==60
    balances={row['month']:row for row in report['monthly_balances']}
    assert balances['2026-10']['overtime_minutes']==60 and balances['2026-11']['remaining_deduction_minutes']==20
