"""补卡行政确认、权限及跨日顺延；仅隔离SQLite，不发送真实通知。"""
from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_chat_participant_access import environment
from test_attendance_clock import arrange,punch,out
from test_attendance import at
from attendance_models import AttendanceClockSession as Clock
from models import AppNotification
import attendance_clock as clock
import attendance_corrections as correction
import attendance_service as attendance


@pytest.fixture
def prepared(environment,monkeypatch):
 db,users=environment;arrange(db,users)
 monkeypatch.setattr(correction,'now',lambda:at('2026-10-28T10:00'))
 monkeypatch.setattr(clock,'now',lambda:at('2026-10-28T10:00'))
 monkeypatch.setattr(correction,'publish',lambda *args:None)
 return db,users


def request(**values):
 return correction.CorrectionWrite(client_id=uuid4(),day='2026-10-28',kind='in',requested_at=at('2026-10-28T09:00'),reason='忘记打卡，需要补充',early_work_confirmed=False,breakfast_after_eating=True,**values)


def test_pending_checkin_no_clock_write_admin_confirmation_and_history(prepared):
 db,(admin,person,other)=prepared
 payload=request();result=correction.submit(db,person,payload);uid=result['record']['id']
 assert db.query(Clock).count()==0
 assert {notice.recipient_user_id for notice in db.query(AppNotification).filter_by(notification_type='attendance_clock_correction')}=={admin.id}
 assert correction.submit(db,person,payload)['record']['id']==uid
 with pytest.raises(HTTPException):correction.confirm(db,other,uid)
 with pytest.raises(HTTPException):correction.listing(db,other,True)
 result=correction.confirm(db,admin,uid)
 row=db.query(Clock).one();assert attendance.stamp(row.check_in)==at('2026-10-28T09:00')
 assert result['record']['status']=='confirmed' and len(result['record']['history'])==2
 assert result['record']['history'][-1]['actor_id']==str(admin.id)
 count=db.query(AppNotification).count();correction.confirm(db,admin,uid);assert db.query(AppNotification).count()==count
 assert correction.listing(db,other)['items']==[]


def test_correct_checkin_keeps_old_values_and_conflict_cannot_overwrite(prepared,monkeypatch):
 db,(admin,person,_)=prepared
 row=punch(db,person,monkeypatch,'2026-10-28T09:30')
 payload=request(record_id=row['id'])
 result=correction.submit(db,person,payload)
 out(db,person,row,monkeypatch,'2026-10-28T18:30')
 with pytest.raises(HTTPException) as changed:correction.confirm(db,admin,result['record']['id'])
 assert changed.value.status_code==409
 correction.cancel(db,person,result['record']['id'])
 new=correction.submit(db,person,payload.model_copy(update={'client_id':uuid4()}));confirmed=correction.confirm(db,admin,new['record']['id'])
 assert confirmed['record']['history'][-1]['before']['check_in']!=confirmed['record']['history'][-1]['after']['check_in']


@pytest.mark.parametrize('checkin,late',[('10:11',0),('10:15',0),('10:16',1)])
def test_checkout_correction_requires_next_start_then_updates_next_day(prepared,monkeypatch,checkin,late):
 db,(admin,person,_)=prepared
 source=punch(db,person,monkeypatch,'2026-10-28T09:00')
 monkeypatch.setattr(correction,'now',lambda:at('2026-10-29T11:00'))
 payload=request().model_dump();payload.update(client_id=uuid4(),kind='out',record_id=source['id'],requested_at=at('2026-10-28T18:30'),next_start=at('2026-10-29T10:00'))
 result=correction.submit(db,person,correction.CorrectionWrite(**payload))
 assert db.query(Clock).one().check_out is None
 correction.confirm(db,admin,result['record']['id'])
 row=punch(db,person,monkeypatch,'2026-10-29T'+checkin)
 assert row['late_minutes']==late and row['shift']['late_start_at'].startswith('2026-10-29T10:00')
 assert len(correction.listing(db,person)['adjustments'])==1


def test_late_checkout_requires_explanation_and_next_start(prepared,monkeypatch):
 db,(admin,person,_)=prepared
 source=punch(db,person,monkeypatch,'2026-10-28T09:00')
 with pytest.raises(HTTPException):out(db,person,source,monkeypatch,'2026-10-29T09:30')
 db.rollback()
 completed=out(db,person,source,monkeypatch,'2026-10-29T09:30',cross_day_reason='跨日工作，后续顺延',next_start=at('2026-10-29T11:00'))
 assert completed['check_out']==at('2026-10-29T09:30')
 assert db.query(correction.AttendanceStartAdjustment).one().reason=='跨日工作，后续顺延'
 following=punch(db,person,monkeypatch,'2026-10-29T11:10');assert following['late_minutes']==0


def test_next_start_required_for_supplemental_checkout(prepared):
 with pytest.raises(ValidationError):correction.CorrectionWrite(**{**request().model_dump(),'kind':'out'})


def test_migration_only_new_tables_and_idempotent(prepared):
 from tools.apply_attendance_corrections_migration import apply_migration
 from home_office_models import HomeOfficeApplicationDuration
 from sqlalchemy import inspect
 db,_=prepared
 for model in [correction.ClockCorrection,correction.AttendanceStartAdjustment,HomeOfficeApplicationDuration]:model.__table__.drop(db.connection())
 db.commit();before=[row['name'] for row in inspect(db.connection()).get_columns('attendance_clock_session')]
 apply_migration(db.connection());apply_migration(db.connection());db.commit()
 assert before==[row['name'] for row in inspect(db.connection()).get_columns('attendance_clock_session')]


def test_http_scope_and_mobile_writes_rejected(prepared):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from database import get_db
 from routers.auth import get_current_user
 db,(admin,person,other)=prepared
 app=FastAPI();app.include_router(correction.router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:person
 payload=request().model_dump(mode='json')
 with TestClient(app) as client:
  assert client.get('/attendance/clock-corrections?company=true').status_code==403
  assert client.post('/attendance/clock-corrections',json=payload,headers={'user-agent':'Mozilla/5.0 (iPhone; Mobile)'}).status_code==403
  result=client.post('/attendance/clock-corrections',json=payload,headers={'user-agent':'Mozilla/5.0 (Windows NT 10.0)'})
  assert result.status_code==200
  uid=result.json()['record']['id']
  assert client.post(f'/attendance/clock-corrections/{uid}/confirm',headers={'user-agent':'Mozilla/5.0 (Windows NT 10.0)'}).status_code==403
  assert client.post('/attendance/clock-corrections',json={**payload,'user_id':str(other.id)},headers={'user-agent':'Mozilla/5.0 (Windows NT 10.0)'}).status_code==422


def test_checkin_correction_preserves_existing_checkout_deductions(prepared,monkeypatch):
 db,(admin,person,_)=prepared
 source=punch(db,person,monkeypatch,'2026-10-28T09:30')
 out(db,person,source,monkeypatch,'2026-10-28T18:30')
 row=db.query(Clock).one();row.confirmations={**row.confirmations,'dinner_eaten':True,'invalid_minutes':10,'invalid_reason':'已有无效时间'};db.commit()
 result=correction.submit(db,person,request(record_id=row.id));correction.confirm(db,admin,result['record']['id'])
 assert row.confirmations['dinner_eaten'] is True and row.confirmations['invalid_minutes']==10 and row.confirmations['invalid_reason']=='已有无效时间'


def test_flexible_shift_does_not_invent_a_midnight_start_time(prepared):
 from types import SimpleNamespace
 db,(_,person,_)=prepared
 row=SimpleNamespace(day=date(2026,10,28),segment=0,shift_snapshot={'code':'flexible','flexible':True,'periods':[]})
 assert correction.next_scheduled_start(db,person,row,at('2026-10-29T10:00'))==(None,0)
