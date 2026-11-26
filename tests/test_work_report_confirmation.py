"""确认报告必须落库，并向有权限的查看人开放。仅隔离内存数据库。"""
from datetime import date, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import get_db
from routers.auth import get_current_user
from routers.tasks import reports_router
from task_models import DailyReport, DailyReportItem
from test_chat_participant_access import environment
import task_service
import work_report_access as access


def test_confirm_persists_and_becomes_visible_only_after_success(environment, monkeypatch):
    db, (owner, viewer, sender) = environment
    owner.username = 'williamzhao'
    db.commit()
    access.save_rule(db, owner, access.AccessRuleWrite(
        name='确认报告验收', viewer_ids=[viewer.id], sender_ids=[sender.id],
    ))
    day = date(2026, 11, 22)
    actual_save_time = datetime(2026, 11, 25, 9, 15)
    monkeypatch.setattr(task_service, 'business_now', lambda: actual_save_time)
    import attendance_service
    shift_days=[]
    def report_shifts(_db,people,shift_day):
        shift_days.append(shift_day)
        return {str(person.id):{'code':'early','label':'早班','periods':['09:00–12:00','13:30–18:30']} for person in people}
    monkeypatch.setattr(attendance_service,'shifts_for',report_shifts)
    report = DailyReport(id=uuid4(), user_id=sender.id, report_date=day, status='draft',
                         generated_at=datetime(2026,11,23,12))
    db.add(report)
    db.commit()
    monkeypatch.setattr(task_service, 'derive_daily_report_items', lambda *_: [])
    monkeypatch.setattr(task_service, 'DailyReportItem', lambda **values: DailyReportItem(id=uuid4(), **values))
    monkeypatch.setattr('routers.auth.user_has_permission', lambda *_: True)
    app = FastAPI()
    app.include_router(reports_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: sender
    item = {
        'source_type': 'manual', 'task_type': '非项目工作', 'task_name': '',
        'progress_content': '核对记录', 'duration_minutes': 30,
        'display_metadata': {'report_types': ['非项目工作'], 'quantity': 1, 'quantity_unit': '次'},
    }
    payload = {'idle_minutes': 30, 'idle_declaration_confirmed': True, 'items': [item]}
    endpoint = f'/daily-reports/{day}/finalize'
    with TestClient(app) as client:
        assert access.received_reports(db, viewer, day, day, None, 1, 20)['total'] == 0
        invalid = {**payload, 'items': [{**item, 'duration_minutes': 0}]}
        assert client.post(endpoint, json=invalid).status_code == 422
        db.expire_all()
        assert db.get(DailyReport, report.id).status == 'draft'
        response = client.post(endpoint, json=payload)
        assert response.status_code == 200, response.text
        assert response.json()['status'] == 'finalized'
        assert response.json()['finalized_at']
        assert response.json()['report_date'] == day.isoformat()
        assert response.json()['saved_at'] == '2026-11-25T09:15:00+08:00'
        assert response.json()['finalized_at'] == '2026-11-25T09:15:00+08:00'
        db.expire_all()
        saved = db.get(DailyReport, report.id)
        assert saved.status == 'finalized'
        assert saved.report_date == day
        assert saved.items[0].progress_content == '核对记录'
        assert access.received_reports(db, viewer, day, day, None, 1, 20)['total'] == 1
        assert access.received_reports(db, viewer, actual_save_time.date(), actual_save_time.date(), None, 1, 20)['total'] == 0
        listed=access.received_reports(db, viewer, day, day, None, 1, 20)['items'][0]
        assert listed['saved_at'].date() == actual_save_time.date()
        assert listed['shift']['label'] == '早班'
        assert shift_days and all(shift_day==day for shift_day in shift_days)
        assert access.received_report(db,viewer,saved.id)['report_date'] == day
        assert client.post(endpoint, json=payload).status_code == 409
        db.rollback()
        assert db.query(DailyReport).filter_by(user_id=sender.id, report_date=day).count() == 1
