"""夜间值班权限、发布隔离、分组打卡与按分钟先抵请假；仅隔离SQLite。"""
from datetime import date
from types import SimpleNamespace
from datetime import datetime
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_monthly_shift import setup
import weekend_night_duty as night
import attendance_clock as clock
import attendance_comp_time as comp


def test_draft_sync_history_and_daytime_consistency(environment,monkeypatch):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    import notification_ws
    monkeypatch.setattr(notification_ws,'broadcast_to_users',lambda *args:None)
    values=[{'user_id':person.id,'date':'2026-11-07','mode':'standalone'}]
    saved=night.mutate(db,admin,'2026-11',night.Write(revision=0,assignments=values))
    assert saved['revision']==1 and saved['needs_sync']
    assert night.get_plan(db,other,'2026-11',True)['assignments']==[]
    assert night.get_plan(db,other,'2026-11',True)['history']==[]
    with pytest.raises(HTTPException):night.mutate(db,other,'2026-11',night.Write(revision=0,assignments=values))
    published=night.mutate(db,admin,'2026-11',night.Version(revision=1),'sync')
    assert not published['can_edit'] and not published['needs_sync']
    assert len(night.get_plan(db,other,'2026-11',True)['history'])==2
    assert night.assignment(db,person.id,date(2026,11,7))['mode']=='standalone'
    with pytest.raises(HTTPException):night.mutate(db,admin,'2026-11',night.Write(revision=1,assignments=[]))
    night.mutate(db,admin,'2026-11',night.Version(revision=1),'edit')
    values[0]['mode']='continuation'
    night.mutate(db,admin,'2026-11',night.Write(revision=1,assignments=values))
    with pytest.raises(HTTPException,match=''):night.mutate(db,admin,'2026-11',night.Version(revision=2),'sync')
    assert night.assignment(db,person.id,date(2026,11,7))['mode']=='standalone'


def test_weekday_invalid_and_wrong_department(environment):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    for who,day in [(person,'2026-11-06'),(other,'2026-11-07')]:
        with pytest.raises(HTTPException):night.mutate(db,admin,'2026-11',night.Write(revision=0,assignments=[{'user_id':who.id,'date':day,'mode':'standalone'}]))
        db.rollback()


def test_continuation_two_separate_clocks_and_home_exemption():
    shift=night.decorate({'periods':['10:30–12:00','13:30–20:00']},{'mode':'continuation'})
    assert clock.segments(shift)==[['10:30–12:00','13:30–18:00'],['19:00–23:00']]
    daytime=clock.snapshot(shift,0);evening=clock.snapshot(shift,1)
    assert not daytime['home_office_day'] and daytime['duty_day_credit']==1
    assert evening['home_office_day'] and evening['duty_day_credit']==0
    assert clock.snapshot(night.decorate(None,{'mode':'standalone'}),0)['duty_day_credit']==0


def test_night_minutes_first_offset_leave_without_half_day_or_baseline_credit():
    duties=[{'id':'night','day':'2026-10-17','minutes':240,'day_credit':0,'direct_extra':True}]
    obligations=[{'id':'leave','day':'2026-10-12','minutes':180}]
    balance=comp.allocation(duties,obligations,[],date(2026,10,1),date(2026,10,30))
    assert balance['duty_days']==0 and balance['average_days']==0
    assert balance['obligations'][0]['makeup_minutes']==180
    assert balance['obligations'][0]['remaining_minutes']==0
    assert balance['duties'][0]['available_minutes']==60
    assert balance['available_minutes']==0  # 白天月均条件未达标，不能直接申请调休
    assert balance['duties'][0]['uses'][0]['kind']=='makeup'
    normal=[{'id':'day1','day':'2026-10-11','minutes':480},{'id':'day2','day':'2026-10-18','minutes':480}]
    balance=comp.allocation(normal+duties,obligations,[{'id':'comp','created_at':'2026-10-20','minutes':120}],date(2026,10,1),date(2026,10,30))
    assert balance['duty_days']==2 and balance['eligible']
    assert balance['available_minutes']==420
    assert balance['obligations'][0]['makeup_links'][0]['duty_id']=='night'


def test_real_continuation_clock_and_no_home_quota_application(environment,monkeypatch):
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    import monthly_shift,weekend_duty
    import weekend_duty_management as daytime
    import notification_ws
    from home_office_models import HomeOfficeApplication
    monkeypatch.setattr(notification_ws,'broadcast_to_users',lambda *args:None)
    monthly_shift.save_plan(db,admin,'2026-11',monthly_shift.PlanWrite(revision=0,assignments=[{'user_id':person.id,'department':'customer','shift':'early'}]))
    saved=weekend_duty.save_plan(db,admin,'2026-11',weekend_duty.DutyWrite(revision=0,assignments=[{'user_id':person.id,'department':'customer','date':'2026-11-07'}]))
    version=SimpleNamespace(revision=saved['revision'],publication_revision=0,fixed_revision=0)
    daytime.publish(db,admin,'2026-11',version)
    night.mutate(db,admin,'2026-11',night.Write(revision=0,assignments=[{'user_id':person.id,'date':'2026-11-07','mode':'continuation'}]))
    night.mutate(db,admin,'2026-11',night.Version(revision=1),'sync')
    request=SimpleNamespace(headers={'user-agent':'Windows NT 10.0'})
    def moment(time):monkeypatch.setattr(clock,'now',lambda:datetime.fromisoformat(f'2026-11-07T{time}:00+08:00'))
    moment('09:00')
    first=clock.check_in(db,person,request,clock.CheckInWrite(segment=0,breakfast_notice_accepted=True))['record']
    assert not first['shift']['home_office_day']
    moment('18:00')
    clock.check_out(db,person,request,clock.CheckOutWrite(record_id=first['id'],early_work_confirmed=False,breakfast_after_eating=True))
    moment('19:00')
    second=clock.check_in(db,person,request,clock.CheckInWrite(segment=1,breakfast_notice_accepted=True))['record']
    assert second['shift']['periods']==['19:00–23:00'] and second['shift']['home_office_day']
    moment('23:00')
    finished=clock.check_out(db,person,request,clock.CheckOutWrite(record_id=second['id'],early_work_confirmed=False,breakfast_after_eating=True,deduct_invalid_time=True,invalid_minutes=20,invalid_reason='中途处理私事'))['record']
    assert finished['invalid_deduction_minutes']==20
    assert db.query(HomeOfficeApplication).count()==0
    assert not clock.today_status(db,person)['can_check_in']
    balance=comp.balances(db,[person],date(2026,11,7))[0]
    assert len(balance['duties'])==2
    night_record=next(row for row in balance['duties'] if row['night_duty'])
    assert night_record['minutes']==220 and night_record['day_credit']==0 and night_record['direct_extra']
    assert balance['duty_days']==1


def test_migration_is_idempotent(environment):
    db,_=environment
    from tools.apply_weekend_night_duty_migration import apply_migration
    apply_migration(db.connection());apply_migration(db.connection())
    assert night.ready(db)


def test_standalone_night_ignores_old_half_day_snapshot_and_uses_valid_minutes(environment):
    db,users=environment;setup(db,users);person=users[1]
    from attendance_models import AttendanceClockSession
    shift=clock.snapshot(night.decorate(None,{'mode':'standalone'}),0)
    shift['duty_day_credit']=0.5  # 已有快照不维护改写，统计按当前规则识别夜间来源。
    db.add(AttendanceClockSession(user_id=person.id,day=date(2026,10,17),segment=0,
        check_in=datetime.fromisoformat('2026-10-17T19:00:00+08:00'),check_out=datetime.fromisoformat('2026-10-17T23:00:00+08:00'),shift_snapshot=shift,
        confirmations={'breakfast_after_eating':True,'early_work_confirmed':False,'invalid_minutes':30,'invalid_reason':'个人事务'}));db.commit()
    value=comp.balances(db,[person],date(2026,10,30))[0]
    assert value['duty_days']==0 and value['extra_minutes']==210
    assert value['duties'][0]['direct_extra'] and value['duties'][0]['day_credit']==0
