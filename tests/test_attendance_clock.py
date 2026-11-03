"""手动打卡、确认、分段、月抵扣与权限；仅隔离 SQLite。"""
from datetime import date
from uuid import UUID,uuid4
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
    return service.check_out(db,user,request(),service.CheckOutWrite(record_id=record['id'],early_work_confirmed=values.pop('early_work_confirmed',True),breakfast_after_eating=values.pop('breakfast_after_eating',True),dinner_eaten=values.pop('dinner_eaten',False),**values))['record']


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


def test_fixed_early_no_dinner_breakfast_violation_and_monthly_offset(environment,monkeypatch):
    db,users=environment;arrange(db,users,fixed=True);admin,person,other=users
    first=punch(db,person,monkeypatch,'2026-10-26T08:00')
    first=out(db,person,first,monkeypatch,'2026-10-26T18:30',breakfast_after_eating=False)
    assert first['raw_overtime_minutes']==60 and first['breakfast_deduction_minutes']==15 and first['dinner_deduction_minutes']==0
    assert first['overtime_minutes']==45 and first['violation_count']==1
    second=punch(db,person,monkeypatch,'2026-10-27T09:00');second=out(db,person,second,monkeypatch,'2026-10-27T18:30')
    assert second['overtime_minutes']==0
    report=attendance.attendance_report(db,person,date(2026,10,26),'month')
    assert report['totals']['overtime_minutes']==45 and report['totals']['violation_count']==1
    balance=report['monthly_balances'][0];assert balance['raw_minutes']==60 and balance['deduction_minutes']==15 and balance['overtime_minutes']==45
    assert {row['user_id'] for row in report['records']}=={str(person.id)}
    assert attendance.attendance_report(db,other,date(2026,10,26),'month')['records']==[]
    with pytest.raises(HTTPException):attendance.attendance_report(db,person,date(2026,10,26),'month',admin=True)


@pytest.mark.parametrize('code,eaten,expected',[('late',True,-20),('late',False,0),('late_late',True,-20),('late_late',False,0)])
@pytest.mark.parametrize('fixed',[False,True])
def test_late_dinner_choice(environment,monkeypatch,code,eaten,expected,fixed):
    db,users=environment;arrange(db,users,code,fixed);person=users[1]
    start,end=('10:30','20:00') if code=='late' else ('13:30','21:30')
    record=punch(db,person,monkeypatch,'2026-10-26T'+start)
    with pytest.raises(HTTPException):out(db,person,record,monkeypatch,'2026-10-26T'+end,dinner_eaten=None)
    record=out(db,person,record,monkeypatch,'2026-10-26T'+end,dinner_eaten=eaten)
    assert record['overtime_minutes']==expected
    assert record['dinner_deduction_minutes']==(20 if eaten else 0)


def test_remote_two_segments_no_dinner_and_invalid_deduction(environment,monkeypatch):
    db,users=environment;arrange(db,users,'customer_remote',True);person=users[1]
    first=punch(db,person,monkeypatch,'2026-10-26T10:00')
    with pytest.raises(HTTPException):punch(db,person,monkeypatch,'2026-10-26T17:00',1)
    first=out(db,person,first,monkeypatch,'2026-10-26T18:00',deduct_invalid_time=True,invalid_minutes=10,invalid_reason='个人事务')
    assert first['dinner_deduction_minutes']==0 and first['overtime_minutes']==20
    second=punch(db,person,monkeypatch,'2026-10-26T20:30',1)
    with pytest.raises(HTTPException):out(db,person,second,monkeypatch,'2026-10-26T23:30',deduct_invalid_time=False,dinner_eaten=None)
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


def completed(db,user,day,start,end,fixed=False,code='early',dinner=None):
    from monthly_shift import SHIFTS
    db.add(Clock(user_id=user.id,day=date.fromisoformat(day),segment=0,check_in=at(day+'T'+start),check_out=at(day+'T'+end),shift_snapshot=service.snapshot({**next(row for row in SHIFTS if row['code']==code),'fixed':fixed},0),confirmations={'early_work_confirmed':True,'breakfast_after_eating':True,'dinner_eaten':dinner}));db.commit()


def test_company_never_offsets_one_person_against_another(environment):
    db,users=environment;arrange(db,users)
    completed(db,users[1],'2026-10-26','10:30','20:00',True,code='late',dinner=True)
    completed(db,users[2],'2026-10-26','09:00','19:30')
    company=attendance.attendance_report(db,users[0],date(2026,10,26),'month',admin=True)
    assert company['totals']['overtime_minutes']==60
    assert next(row for row in company['monthly_balances'] if row['user_id']==str(users[1].id))['remaining_deduction_minutes']==20


def test_week_spanning_months_never_transfers_deductions_between_months(environment):
    db,users=environment;arrange(db,users)
    completed(db,users[1],'2026-10-30','09:00','19:30')
    completed(db,users[1],'2026-11-01','10:30','20:00',True,code='late',dinner=True)
    report=attendance.attendance_report(db,users[1],date(2026,10,26),'week')
    assert report['totals']['overtime_minutes']==60
    balances={row['month']:row for row in report['monthly_balances']}
    assert balances['2026-10']['overtime_minutes']==60 and balances['2026-11']['remaining_deduction_minutes']==20

@pytest.mark.parametrize('legacy',[False,True])
@pytest.mark.parametrize('code',['early','customer_remote'])
def test_previous_missing_checkout_allows_today_and_blocks_stale_checkout(environment,monkeypatch,legacy,code):
    db,users=environment;arrange(db,users,code);person=users[1]
    previous=punch(db,person,monkeypatch,'2026-10-26T10:30')
    if legacy:
        row=db.get(Clock,UUID(previous['id']));old=AttendanceDay(user_id=person.id,day=row.day,check_in=row.check_in,shift_snapshot=row.shift_snapshot)
        db.delete(row);db.add(old);db.commit();previous['id']=str(old.id)
    monkeypatch.setattr(service,'now',lambda:at('2026-10-27T10:30'))
    status=service.today_status(db,person)
    assert status['can_check_in'] and status['can_home_overtime_check_in']
    assert status['pending_previous']['id']==previous['id']
    today=punch(db,person,monkeypatch,'2026-10-27T10:30')
    assert today['day']=='2026-10-27'
    assert punch(db,person,monkeypatch,'2026-10-27T10:31')['id']==today['id']
    with pytest.raises(HTTPException) as error:
        out(db,person,previous,monkeypatch,'2026-10-27T11:00')
    assert error.value.status_code==409 and '补下班打卡' in error.value.detail
    db.rollback()
    assert service.today_status(db,person)['record']['id']==today['id']
    options={'deduct_invalid_time':False} if code=='customer_remote' else {}
    out(db,person,today,monkeypatch,'2026-10-27T18:30',**options)
    assert service.today_status(db,person)['record']['check_out'] is not None
    model=AttendanceDay if legacy else Clock
    assert db.get(model,UUID(previous['id'])).check_out is None


def test_multiple_missing_days_and_home_overtime(environment,monkeypatch):
    db,users=environment;arrange(db,users);person=users[1]
    first=punch(db,person,monkeypatch,'2026-10-26T09:00')
    second=punch(db,person,monkeypatch,'2026-10-27T09:00')
    monkeypatch.setattr(service,'now',lambda:at('2026-10-28T21:00'))
    assert service.today_status(db,person)['can_home_overtime_check_in']
    result=service.check_in(db,person,request(),service.CheckInWrite(breakfast_notice_accepted=True,work_mode='company_home_overtime'))['record']
    assert result['day']=='2026-10-28' and result['segment']==2
    assert not service.today_status(db,person)['can_check_in']
    with pytest.raises(HTTPException):punch(db,person,monkeypatch,'2026-10-28T21:01')
    assert db.query(Clock).filter(Clock.check_out.is_(None)).count()==3


def test_older_legacy_missing_checkout_remains_visible_after_today(environment,monkeypatch):
    db,users=environment;arrange(db,users);person=users[1]
    old=AttendanceDay(user_id=person.id,day=date(2026,10,26),check_in=at('2026-10-26T09:00'),shift_snapshot=attendance.shift_for(db,person,date(2026,10,26)))
    db.add(old);db.commit()
    monkeypatch.setattr(service,'now',lambda:at('2026-10-28T09:00'))
    status=service.today_status(db,person)
    assert status['pending_previous']['id']==str(old.id) and status['can_check_in']
    today=punch(db,person,monkeypatch,'2026-10-28T09:00')
    status=service.today_status(db,person)
    assert status['pending_previous']['id']==str(old.id) and status['record']['id']==today['id']
    assert not status['record']['requires_cross_day_reason']

@pytest.mark.parametrize('time,late,minutes',[('09:15:00',False,0),('09:15:01',True,0.02),('09:16:00',True,1),('09:15:00.001',True,0)])
def test_check_in_preview_boundary_read_only_and_submit(environment,monkeypatch,time,late,minutes):
    db,users=environment;arrange(db,users);person=users[1]
    monkeypatch.setattr(service,'now',lambda:at('2026-10-26T'+time))
    preview=service.today_status(db,person)['check_in_preview']
    assert preview=={'is_late':late,'late_minutes':minutes}
    assert db.query(Clock).count()==0 and db.query(AttendanceDay).count()==0
    result=service.check_in(db,person,request(),service.CheckInWrite(breakfast_notice_accepted=True))
    assert bool(result['record']['late_count'])==late and result['record']['late_minutes']==minutes
    assert result['message'].startswith('迟到打卡成功' if late else '上班打卡成功')
    assert 'check_in_preview' not in service.today_status(db,person)


def test_preview_does_not_determine_final_checkin(environment,monkeypatch):
    db,users=environment;arrange(db,users);person=users[1]
    monkeypatch.setattr(service,'now',lambda:at('2026-10-26T09:15'))
    assert not service.today_status(db,person)['check_in_preview']['is_late']
    result=punch(db,person,monkeypatch,'2026-10-26T09:16')
    assert result['late_minutes']==1 and result['late_count']==1


@pytest.mark.parametrize('scenario',['leave','break','override','second_segment','flexible','continuation'])
def test_preview_reuses_existing_attendance_rules(environment,monkeypatch,scenario):
    from types import SimpleNamespace
    import attendance_corrections
    db,users=environment;arrange(db,users);person=users[1]
    moment='2026-10-26T10:16'
    if scenario=='leave':
        monkeypatch.setattr(attendance,'day_leaves',lambda *args:[SimpleNamespace(start_date=at('2026-10-26T09:00'),end_date=at('2026-10-26T10:00'),reason='请假')])
    elif scenario=='override':
        monkeypatch.setattr(attendance_corrections,'start_override',lambda *args:{'late_start_at':'2026-10-26T10:00:00+08:00'})
    elif scenario=='break':moment='2026-10-26T13:00'
    elif scenario=='second_segment':
        monkeypatch.setattr(attendance,'shift_for',lambda *args:{'code':'customer_remote','label':'居家晚班','periods':['10:30–12:00','13:30–18:00','21:00–23:00']})
        first=punch(db,person,monkeypatch,'2026-10-26T10:30')
        out(db,person,first,monkeypatch,'2026-10-26T18:00',deduct_invalid_time=False)
        moment='2026-10-26T21:16'
    else:
        from test_fixed_shift_types import configure
        configure(db,users,'flexible' if scenario=='flexible' else 'fixed_early_early',monkeypatch)
        if scenario=='continuation':
            first=punch(db,person,monkeypatch,'2026-10-26T08:30')
            out(db,person,first,monkeypatch,'2026-10-26T09:00')
    monkeypatch.setattr(service,'now',lambda:at(moment))
    status=service.today_status(db,person);preview=status['check_in_preview']
    result=punch(db,person,monkeypatch,moment,status['next_segment'])
    expected=165 if scenario=='break' else 0 if scenario in ('flexible','continuation') else 1
    assert result['late_minutes']==expected
    assert preview=={'is_late':bool(result['late_count']),'late_minutes':expected}



@pytest.mark.parametrize('code',['early','late','late_late','customer_remote','flexible','management','company_home_overtime'])
@pytest.mark.parametrize('end,eaten,expected',[
    ('2026-10-26T18:49:00',True,0),('2026-10-26T18:50:00',True,0),
    ('2026-10-26T18:50:01',True,20),('2026-10-26T19:00:00',False,0),
    ('2026-10-27T02:00:00',True,20)])
def test_dinner_actual_checkout_boundary_all_shifts_and_next_day(monkeypatch,code,end,eaten,expected):
    from types import SimpleNamespace
    monkeypatch.setattr(service,'home_office_day',lambda *args:{})
    shift={'code':code,'periods':['09:00–18:30'],'fixed':True,'flexible':code=='flexible','home_office_day':code in ('customer_remote','company_home_overtime')}
    row=SimpleNamespace(id=uuid4(),user_id=uuid4(),day=date(2026,10,26),segment=0,check_in=at('2026-10-26T09:00'),check_out=at(end),shift_snapshot=shift,confirmations={'breakfast_after_eating':True,'dinner_eaten':eaten})
    result=service.serialize(row)
    assert result['dinner_deduction_minutes']==expected
    payload=service.CheckOutWrite(record_id=row.id,early_work_confirmed=False,breakfast_after_eating=True,dinner_eaten=None,deduct_invalid_time=False if shift['home_office_day'] else None)
    if service.dinner_confirmation_required(row.day,row.check_out):
        with pytest.raises(HTTPException) as error:service.validate_checkout(None,None,row,payload,row.check_out)
        assert '18:50' in error.value.detail
    else:service.validate_checkout(None,None,row,payload,row.check_out)


def test_dinner_once_across_regular_and_company_home_overtime(environment,monkeypatch):
    db,users=environment;arrange(db,users);person=users[1]
    first=punch(db,person,monkeypatch,'2026-10-26T09:00')
    first=out(db,person,first,monkeypatch,'2026-10-26T19:00',dinner_eaten=True)
    assert first['dinner_deduction_minutes']==20
    monkeypatch.setattr(service,'now',lambda:at('2026-10-26T20:00'))
    second=service.check_in(db,person,request(),service.CheckInWrite(breakfast_notice_accepted=True,work_mode='company_home_overtime'))['record']
    second=out(db,person,second,monkeypatch,'2026-10-26T21:00',dinner_eaten=True,deduct_invalid_time=False)
    assert second['dinner_deduction_minutes']==0 and second['shift']['dinner_already_deducted']
