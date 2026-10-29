"""手机延迟上班、全体通知原子性和其他操作手机限制。"""
from datetime import date
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_chat_participant_access import environment
from test_monthly_shift import setup
from test_attendance import at
from models import AppNotification,ChatProjectMessage
import attendance_delay_start as service


def test_mobile_submit_notifies_everyone_once_and_private_history(environment,monkeypatch):
    from routers.attendance import router
    from routers.monthly_shifts import router as shift_router
    from routers.auth import get_current_user
    from database import get_db
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    monkeypatch.setattr(service,'now',lambda:at('2026-10-28T08:00'))
    app=FastAPI();app.include_router(router);app.include_router(shift_router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:person
    value={'client_id':str(uuid4()),'requested_start':'2026-10-28T10:00:00+08:00','reason':'交通拥堵'}
    headers={'user-agent':'iPhone Mobile','x-client-type':'mobile'}
    with TestClient(app) as client:
        first=client.post('/attendance/delay-start',json=value,headers=headers);assert first.status_code==200
        assert client.post('/attendance/delay-start',json=value,headers=headers).status_code==200
        assert db.query(service.DelayStart).count()==1
        assert db.query(AppNotification).filter_by(notification_type='attendance_delay_start').count()==3
        from schemas import NotificationResponse
        notice=db.query(AppNotification).filter_by(notification_type='attendance_delay_start').first()
        assert NotificationResponse.model_validate(notice).model_dump(mode='json')['created_at'].endswith('+08:00')
        assert db.query(ChatProjectMessage).filter_by(message_type='attendance_delay_start').count()==2
        assert len(client.get('/attendance/delay-start').json()['items'])==1
        app.dependency_overrides[get_current_user]=lambda:other
        assert client.get('/attendance/delay-start').json()['items']==[]
        assert client.post('/attendance/delay-start',json=value,headers=headers).status_code==409
        assert client.post('/attendance/home-office/qualification',json={'client_id':str(uuid4()),'reason':'理由'},headers=headers).status_code==403
        assert client.post('/attendance/home-office/apply',json={'client_id':str(uuid4()),'requested_date':'2026-10-28'},headers=headers).status_code==403
        assert client.put('/attendance/home-office/usage',json={'user_id':str(other.id),'year':2026,'used_days':0,'revision':0},headers=headers).status_code==403
        shifted=client.put('/monthly-shifts/weekly?week=2026-10-26',json={'revision':0,'assignments':[]},headers=headers)
        assert shifted.status_code==403 and '手机' in shifted.json()['detail']


def test_reason_timezone_and_notification_failure(environment,monkeypatch):
    import attendance_notifications
    db,(admin,person,other)=environment;setup(db,[admin,person,other]);monkeypatch.setattr(service,'now',lambda:at('2026-10-28T08:00'))
    with pytest.raises(ValidationError):service.DelayWrite(client_id=uuid4(),requested_start='2026-10-28T10:00',reason='理由')
    with pytest.raises(ValidationError):service.DelayWrite(client_id=uuid4(),requested_start='2026-10-28T10:00+08:00',reason=' ')
    payload=service.DelayWrite(client_id=uuid4(),requested_start='2026-10-28T10:00+08:00',reason='交通拥堵')
    monkeypatch.setattr(attendance_notifications,'queue_attendance_notifications',lambda *a:(_ for _ in ()).throw(RuntimeError('隔离通知失败')))
    with pytest.raises(RuntimeError):service.submit(db,person,payload)
    assert db.query(service.DelayStart).count()==0


def test_delay_migration_idempotent(environment):
    from tools.apply_attendance_delay_start_migration import apply_migration
    db,users=environment
    service.DelayStart.__table__.drop(db.connection());db.commit();apply_migration(db.connection());apply_migration(db.connection());db.commit()
    assert service.ready(db)
