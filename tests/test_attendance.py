"""电脑登录、签退、午休/请假交集、周/月汇总及通知原子性；仅隔离 SQLite。"""
from datetime import date,datetime,timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from sqlalchemy import create_engine,inspect
from test_chat_participant_access import environment
from test_monthly_shift import setup,payload,sync
from chat_time import BUSINESS_TIMEZONE
from models import AppNotification,ChatProjectMessage,EmployeeLeave
from attendance_models import AttendanceDay,AttendanceLeave
import attendance_service as service
import weekly_shift
import attendance_clock as clock

def at(value):return datetime.fromisoformat(value).replace(tzinfo=BUSINESS_TIMEZONE)
def request(mobile=False):return Request({'type':'http','headers':[(b'user-agent',b'Mozilla/5.0 (iPhone; Mobile)' if mobile else b'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'),(b'x-client-type',b'mobile' if mobile else b'desktop')]})
def day(start='09:00',end='18:30',code='early'):
    from monthly_shift import SHIFTS
    return SimpleNamespace(day=date(2026,10,26),check_in=at(f'2026-10-26T{start}:00'),check_out=at(f'2026-10-26T{end}:00') if end else None,shift_snapshot=next(row for row in SHIFTS if row['code']==code))
def leave(start,end):return SimpleNamespace(start_date=at(start).replace(tzinfo=None),end_date=at(end).replace(tzinfo=None))

@pytest.mark.parametrize('clock,late',[('09:00',0),('09:10',0),('09:11',0),('09:15',0),('09:16',1),('09:45',30),('13:45',180)])
def test_lateness_grace_excludes_lunch(clock,late):
    assert service.metrics(day(clock))['late_minutes']==late

def test_overtime_excludes_lunch_gaps_and_leave():
    result=service.metrics(day(end='19:30'))
    assert result['overtime_minutes']==60 and result['lunch_deducted_minutes']==90
    assert service.metrics(day('10:30','23:00','customer_remote'))['overtime_minutes']==0
    assert service.metrics(day('09:11'))['overtime_minutes']==0
    assert service.metrics(day(end=None))['overtime_minutes']==0
    absence=leave('2026-10-26T09:00','2026-10-26T10:00')
    result=service.metrics(day('10:15','18:30'),[absence])
    assert result['late_minutes']==0 and result['overtime_minutes']==0
    result=service.metrics(day('09:00','19:30'),[absence])
    assert result['overtime_minutes']==60

@pytest.fixture
def arranged(environment,monkeypatch):
    db,users=environment;setup(db,users)
    monkeypatch.setattr(service,'now',lambda:at('2026-10-26T09:11:00'))
    monkeypatch.setattr(clock,'now',lambda:service.now())
    weekly_shift.save_plan(db,users[0],'2026-10-26',weekly_shift.WeeklyPlanWrite(revision=0,assignments=payload(users[1]).assignments))
    sync(db,users[0],'2026-10-26')
    return db,users

def test_manual_punch_only_and_committed_checkout(arranged,monkeypatch):
    db,(admin,person,other)=arranged
    assert service.auto_check_in(db,person,request(True))['status']=='mobile'
    assert service.auto_check_in(db,person,request())['status']=='manual_required'
    assert db.query(AttendanceDay).count()==0
    value=clock.check_in(db,person,request(),clock.CheckInWrite(breakfast_notice_accepted=True))
    assert value['record']['check_in'].hour==9
    monkeypatch.setattr(service,'now',lambda:at('2026-10-26T19:30:00'))
    record=value['record'];data=clock.CheckOutWrite(record_id=record['id'],early_work_confirmed=True,breakfast_after_eating=True)
    with pytest.raises(HTTPException) as error:service.check_out(db,person,request(True),data)
    assert error.value.status_code==403
    value=service.check_out(db,person,request(),data)
    first=value['record']['check_out'];assert first is not None
    monkeypatch.setattr(service,'now',lambda:at('2026-10-26T20:30:00'))
    assert service.check_out(db,person,request(),data)['record']['check_out']==first
    with pytest.raises(HTTPException):service.check_out(db,other,request(),data)


def test_leave_preview_save_notify_idempotency_and_stats(arranged,monkeypatch):
    db,(admin,person,other)=arranged
    events=[]
    import notification_ws
    monkeypatch.setattr(notification_ws,'dispatch_personal_message',lambda uid,event:events.append((uid,event)))
    data=service.LeaveWrite(client_id=uuid4(),start_at=at('2026-10-26T09:00'),end_at=at('2026-10-26T14:30'),reason='隔离测试请假')
    assert service.preview_leave(db,person,data)['minutes']==240
    value=service.create_leave(db,person,data)
    assert value['minutes']==240
    assert db.query(EmployeeLeave).count()==1 and db.query(AttendanceLeave).count()==1
    assert db.query(AppNotification).filter_by(notification_type='attendance_leave').count()==3
    assert db.query(ChatProjectMessage).filter_by(message_type='attendance_leave').count()==2
    assert len({uid for uid,event in events if event['type']=='notification'})==3
    assert service.create_leave(db,person,data)['id']==value['id']
    assert db.query(ChatProjectMessage).count()==2
    with pytest.raises(HTTPException) as conflict:service.create_leave(db,person,data.model_copy(update={'client_id':uuid4()}))
    assert conflict.value.status_code==409
    assert weekly_shift.my_plan(db,person,'2026-10-26')['assignment']['leave_minutes']==240
    for period in ('week','month'):
        report=service.attendance_report(db,person,date(2026,10,26),period)
        assert report['totals']['leave_minutes']==240
        assert len(report['records'])==1 and report['records'][0]['leaves'][0]['reason']=='隔离测试请假'
        assert {row['user_id'] for row in report['people']}=={str(person.id)}
    assert service.attendance_report(db,other,date(2026,10,26),'week')['records']==[]
    with pytest.raises(HTTPException):service.attendance_report(db,person,date(2026,10,26),'week',admin=True)
    assert service.attendance_report(db,admin,date(2026,10,26),'week',admin=True,keyword='member')['totals']['leave_minutes']==240

def test_failed_notification_transaction_does_not_save_leave(arranged,monkeypatch):
    db,(admin,person,other)=arranged
    import attendance_notifications
    monkeypatch.setattr(attendance_notifications,'queue_leave_notifications',lambda *args:(_ for _ in ()).throw(RuntimeError('isolated notification failure')))
    value=service.LeaveWrite(client_id=uuid4(),start_at=at('2026-10-26T09:00'),end_at=at('2026-10-26T10:00'),reason='测试')
    with pytest.raises(RuntimeError):service.create_leave(db,person,value)
    db.rollback()
    assert db.query(EmployeeLeave).count()==0 and db.query(AttendanceLeave).count()==0

def test_no_lunch_only_leave_and_no_mobile_or_offday_clock(arranged,monkeypatch):
    db,(admin,person,other)=arranged
    data=service.LeaveWrite(client_id=uuid4(),start_at=at('2026-10-26T12:00'),end_at=at('2026-10-26T13:30'),reason='测试')
    with pytest.raises(HTTPException):service.create_leave(db,person,data)
    monkeypatch.setattr(service,'now',lambda:at('2026-10-25T09:00'))
    assert service.auto_check_in(db,person,request())['status']=='manual_required'
    mobile_desktop_ua=Request({'type':'http','headers':[(b'user-agent',b'Mozilla Macintosh'),(b'x-client-type',b'mobile')]})
    assert not service.desktop_request(mobile_desktop_ua)

def test_migration_is_idempotent_without_existing_table_changes():
    from tools.apply_attendance_migration import apply_migration
    from models import AppUser
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        # 被引用表只需主键；迁移不得改已有表。
        from sqlalchemy import text
        connection.execute(text('CREATE TABLE app_user (id UUID PRIMARY KEY)'))
        apply_migration(connection);apply_migration(connection)
        assert inspect(connection).has_table('attendance_day') and inspect(connection).has_table('attendance_leave')
        assert [row['name'] for row in inspect(connection).get_columns('app_user')]==['id']
        assert any(row['name']=='uq_attendance_user_day' for row in inspect(connection).get_unique_constraints('attendance_day'))
    engine.dispose()

def test_login_hook_and_report_api_do_not_accept_other_user(arranged,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers import auth
    from routers.attendance import router
    db,(admin,person,other)=arranged
    monkeypatch.setattr(auth,'authenticate_user',lambda *args,**kwargs:person)
    monkeypatch.setattr(auth,'get_user_roles_with_role_names',lambda *args:[])
    monkeypatch.setattr(auth,'get_user_permission_codes',lambda *args:[])
    app=FastAPI();app.include_router(auth.router);app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[auth.get_current_user]=lambda:person
    with TestClient(app) as client:
        headers={'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)','x-client-type':'desktop'}
        value=client.post('/auth/login/json',json={'username':person.username,'password':'test'},headers=headers)
        assert value.status_code==200 and value.json()['attendance']['status']=='manual_required'
        assert client.post('/attendance/check-in',json={'breakfast_notice_accepted':True},headers=headers).status_code==200
        assert client.get(f'/attendance/mine?anchor=2026-10-26&period=week&user_id={other.id}').json()['records'][0]['user_id']==str(person.id)
        assert client.get('/attendance/report?anchor=2026-10-26').status_code==403
        assert client.post('/attendance/check-out',json={'record_id':str(db.query(clock.Clock).one().id),'early_work_confirmed':True,'breakfast_after_eating':True},headers={'user-agent':'iPhone Mobile','x-client-type':'desktop'}).status_code==403
        assert client.post('/attendance/arrival',headers=headers).json()['status']=='manual_required'
        value={'client_id':str(uuid4()),'start_at':'2026-10-26T10:00:00+08:00','end_at':'2026-10-26T11:00:00+08:00','reason':'手机请假测试'}
        assert client.post('/attendance/leave',json=value,headers={'user-agent':'iPhone Mobile'}).status_code==200
