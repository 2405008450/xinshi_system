from datetime import datetime
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import inspect
from test_technical_development import environment, setup, payload
from chat_time import BUSINESS_TIMEZONE
import technical_development as tasks
import development_feedback as feedback


def sheet(setup):
    db, (developer, executor, reporter) = setup
    task = tasks.create_task(db, developer, payload(developer, executor))
    value = feedback.generate_sheet(db, developer, task['id'])
    return db, developer, executor, reporter, task, value


def test_generate_each_level_idempotently_and_company_can_submit(setup, monkeypatch):
    db, (developer, executor, reporter) = setup
    monkeypatch.setattr(feedback, 'now', lambda: datetime(2026, 10, 30, 23, 59, tzinfo=BUSINESS_TIMEZONE))
    parent = None
    for level in range(3):
        task = tasks.create_task(db, developer, payload(developer, executor, f'第{level+1}级任务', parent_id=parent))
        parent = task['id']
        result = feedback.generate_sheet(db, developer, task['id'])
        assert not result['already_exists']
        assert feedback.generate_sheet(db, developer, task['id'])['already_exists']
    catalog = feedback.catalog(db, reporter)
    assert len(catalog['groups']) == 3
    assert catalog['access'] == dict(william=False, development=False)
    assert [group['items'][0]['feedback_no'] for group in catalog['groups']] == ['FB-261030-001','FB-261030-002','FB-261030-003']
    request = feedback.CreateFeedback(request_id=uuid4())
    row = feedback.create(db, reporter, parent, request)
    assert row['feedback_no'] == 'FB-261030-004'
    assert row['submitted_by'] == reporter.id and row['submitted_username'] == reporter.username
    assert row['submitted_on'].isoformat() == '2026-10-30'
    assert row['created_at'].utcoffset().total_seconds() == 28800
    assert feedback.create(db, reporter, parent, request)['id'] == row['id']
    monkeypatch.setattr(feedback, 'now', lambda: datetime(2026, 10, 31, 0, 1, tzinfo=BUSINESS_TIMEZONE))
    assert feedback.create(db, reporter, parent, feedback.CreateFeedback(request_id=uuid4()))['feedback_no'] == 'FB-261031-001'
    with pytest.raises(HTTPException): feedback.generate_sheet(db, reporter, parent)
    with pytest.raises(HTTPException): feedback.create(db, reporter, uuid4(), request)


def test_field_validation_versions_assignee_and_author_permissions(setup):
    db, developer, executor, reporter, task, _ = sheet(setup)
    row = feedback.create(db, reporter, task['id'], feedback.CreateFeedback(request_id=uuid4()))
    updated = feedback.update(db, reporter, row['id'], feedback.PatchFeedback(revision=1, module='工作报告', content='显示有误', urgency='紧急', attachments='https://example.com/image.png', status='处理中', assignee_id=executor.id, result='已定位', completed_on='2026-10-31', notes='回归验证'))
    assert updated['revision'] == 2 and updated['urgency'] == '紧急' and updated['assignee_name'] == executor.full_name
    assert updated['submitted_by'] == reporter.id and updated['submitted_username'] == reporter.username
    with pytest.raises(HTTPException) as stale: feedback.update(db, developer, row['id'], feedback.PatchFeedback(revision=1, content='旧值'))
    assert stale.value.status_code == 409
    with pytest.raises(HTTPException): feedback.update(db, reporter, row['id'], feedback.PatchFeedback(revision=2, assignee_id=reporter.id))
    foreign = feedback.catalog(db, reporter)['groups'][0]['items'][0]
    assert not foreign['can_edit']
    with pytest.raises(HTTPException) as denied: feedback.update(db, reporter, foreign['id'], feedback.PatchFeedback(revision=1, notes='不应写入他人反馈'))
    assert denied.value.status_code == 403
    for bad in [dict(urgency='超高'),dict(status='已关闭'),dict(submitted_by=developer.id),dict(feedback_no='FB-伪造')]:
        with pytest.raises(ValidationError): feedback.PatchFeedback(revision=2, **bad)


def test_opinions_are_named_append_only_and_scoped(setup):
    db, developer, executor, william, task, result = sheet(setup)
    william.username = 'williamzhao'; william.full_name = 'William'; db.commit()
    row_id = result['feedback_id']
    first = feedback.add_opinion(db, developer, row_id, feedback.OpinionWrite(kind='development', content='第一次意见'))
    opinion = first['opinions'][0]
    assert opinion['author_id'] == developer.id and opinion['author_username'] == developer.username
    assert opinion['created_at'].utcoffset().total_seconds() == 28800
    second = feedback.add_opinion(db, executor, row_id, feedback.OpinionWrite(kind='development', content='补充意见', expected_latest_id=opinion['id']))
    assert len(second['opinions']) == 2 and second['opinions'][0]['author_id'] == executor.id
    with pytest.raises(HTTPException) as stale: feedback.add_opinion(db, developer, row_id, feedback.OpinionWrite(kind='development', content='陈旧意见'))
    assert stale.value.status_code == 409
    with pytest.raises(HTTPException): feedback.add_opinion(db, developer, row_id, feedback.OpinionWrite(kind='william', content='伪造William意见'))
    with pytest.raises(HTTPException): feedback.add_opinion(db, william, row_id, feedback.OpinionWrite(kind='development', content='伪造开发意见'))
    third = feedback.add_opinion(db, william, row_id, feedback.OpinionWrite(kind='william', content='William建议'))
    assert len(third['opinions']) == 3 and third['opinions'][0]['author_username'] == 'williamzhao'
    assert feedback.catalog(db, william)['access'] == dict(william=True, development=False)


def test_new_table_migration_idempotent_and_does_not_touch_tasks(setup):
    db, developer, executor, _, task, _ = sheet(setup)
    from tools.apply_development_feedback_migration import apply_migration
    for table in reversed(feedback.TABLES): table.drop(db.connection())
    db.commit()
    before = tasks.detail(db, developer, task['id'])
    apply_migration(db.connection()); apply_migration(db.connection()); db.commit()
    assert all(inspect(db.connection()).has_table(table.name) for table in feedback.TABLES)
    assert feedback.catalog(db, developer)['groups'] == []
    assert tasks.detail(db, developer, task['id']) == before


def test_http_contract_and_inactive_denied(setup):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.development_feedback import router
    db, developer, _, reporter, task, _ = sheet(setup)
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: reporter
    client = TestClient(app)
    assert client.get('/development-feedback').status_code == 200
    assert client.post(f"/development-feedback/tasks/{task['id']}/generate").status_code == 403
    response = client.post(f"/development-feedback/tasks/{task['id']}/rows", json={'request_id': str(uuid4())})
    assert response.status_code == 200 and response.json()['created_at'].endswith('+08:00')
    row_id = response.json()['id']
    assert client.patch(f'/development-feedback/rows/{row_id}', json={'revision':1,'notes':'普通人员意见'}).status_code == 200
    assert client.post(f'/development-feedback/rows/{row_id}/opinions', json={'kind':'william','content':'伪造'}).status_code == 403
    reporter.is_active = False; db.commit()
    assert client.get('/development-feedback').status_code == 403
