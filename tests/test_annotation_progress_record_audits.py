"""进度记录协作修改与留痕，使用隔离内存数据库。"""
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from test_chat_participant_access import environment, project


@pytest.fixture
def progress_context(environment, monkeypatch):
    from models import AppUser
    from annotation_ops_models import AnnotationProjectStatusHistory
    from project_audit_models import ProjectOperationAudit
    from annotation_progress_time import business_now
    from routers.annotation_ops import router
    from routers.auth import get_current_user
    from database import get_db
    db, users = environment
    parent = project(db, users[0])
    now = datetime(2026, 10, 25, 10, 30)
    rows = [AnnotationProjectStatusHistory(id=uuid4(), project_id=parent.id,
        from_status='trial_preparation', to_status='trial_preparation' if kind == 'progress' else 'trial_in_progress',
        effective_on=now, changed_at=now, updated_at=now, changed_by=users[0].id,
        entry_kind=kind, change_note='原始内容') for kind in ['progress', 'status']]
    db.add_all(rows); db.commit()
    def audit_defaults(_mapper, _connection, row):
        row.id = row.id or uuid4()
        row.occurred_at = business_now()
    event.listen(ProjectOperationAudit, 'before_insert', audit_defaults)
    app = FastAPI()
    app.include_router(router)
    actor = [users[1]]
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: actor[0]
    monkeypatch.setattr('routers.auth.get_user_permission_codes', lambda _db, uid: ['projects:read'] if uid == users[1].id else [])
    try:
        yield db, parent, rows, TestClient(app), actor, users
    finally:
        event.remove(ProjectOperationAudit, 'before_insert', audit_defaults)


def test_readonly_user_can_edit_other_users_record_and_audit_diff(progress_context):
    from project_audit_models import ProjectOperationAudit
    db, parent, (row, _status), client, actor, users = progress_context
    before_version = row.updated_at.isoformat()
    url = f'/annotation-ops/status-history/{row.id}/progress'
    result = client.patch(url, json={'effective_on':'2026-10-25T11:30:00+08:00',
        'change_note':'协作修改后的内容', 'expected_updated_at':before_version, 'reason':'修正信息'})
    assert result.status_code == 200, result.text
    db.refresh(row)
    assert row.changed_by == users[0].id and row.updated_by == users[1].id
    assert row.change_note == '协作修改后的内容'
    audit = db.query(ProjectOperationAudit).one()
    assert audit.operation_type == 'progress_edit' and audit.actor_user_id == users[1].id
    history = client.get(f'/annotation-ops/projects/{parent.id}/progress-record-audits')
    assert history.status_code == 200
    item = history.json()[0]
    assert item['before']['change_note'] == '原始内容'
    assert item['after']['change_note'] == row.change_note
    assert item['occurred_at'].endswith('+08:00')
    assert item['before']['effective_on'].endswith('+08:00')
    stale = client.patch(url, json={'effective_on':'2026-10-25T11:30:00+08:00',
        'change_note':'旧版本不能覆盖', 'expected_updated_at':before_version})
    assert stale.status_code == 409
    assert db.query(ProjectOperationAudit).count() == 1
    actor[0] = users[2]
    assert client.patch(url, json={'effective_on':'2026-10-25T11:30:00+08:00','change_note':'无权限'}).status_code == 403


def test_delete_keeps_placeholder_and_audit_only_for_same_project(progress_context):
    from annotation_ops_models import AnnotationProjectStatusHistory
    from annotation_ops_service import list_status_history
    db, parent, (row, _status), client, _actor, users = progress_context
    rid = row.id
    response = client.request('DELETE',f'/annotation-ops/status-history/{rid}/progress',
        json={'reason':'重复记录','expected_updated_at':row.updated_at.isoformat()})
    assert response.status_code == 200, response.text
    assert db.get(AnnotationProjectStatusHistory, rid) is None
    tombstone = next(item for item in response.json() if item['id'] == str(rid))
    assert tombstone['is_deleted'] and tombstone['change_note'] is None
    other = project(db, users[0], 'AP-OTHER')
    assert not list_status_history(db, other.id)
    assert client.get(f'/annotation-ops/projects/{other.id}/progress-record-audits').json() == []


def test_status_note_edit_delete_does_not_change_status_or_transition_time(progress_context):
    from annotation_ops_models import AnnotationProjectStatusHistory
    db, parent, (_progress, row), client, _actor, _users = progress_context
    original_status, original_time = parent.project_status, row.effective_on
    url = f'/annotation-ops/status-history/{row.id}/progress'
    edited = client.patch(url, json={'effective_on':'2026-10-26T10:00:00+08:00','change_note':'补正变更说明',
        'record_part':'status_note','expected_updated_at':row.updated_at.isoformat()})
    assert edited.status_code == 200, edited.text
    db.refresh(row)
    assert row.effective_on == original_time and row.entry_kind == 'status'
    deleted = client.request('DELETE',url,json={'reason':'说明重复','record_part':'status_note',
        'expected_updated_at':row.updated_at.isoformat()})
    assert deleted.status_code == 200, deleted.text
    db.refresh(row); db.refresh(parent)
    assert row.change_note is None and db.get(AnnotationProjectStatusHistory, row.id)
    assert parent.project_status == original_status and row.effective_on == original_time
    assert next(item for item in deleted.json() if item['id'] == str(row.id))['note_deleted']


def test_legacy_deleted_snapshot_is_timezone_normalized():
    from annotation_progress_record_audit import audit_response
    from types import SimpleNamespace
    row = SimpleNamespace(id=uuid4(),operation_type='progress_delete',actor_name_snapshot='人员',
        actor_username_snapshot='user',occurred_at=datetime(2026,10,25,10),change_reason='重复',
        project_snapshot={'deleted_progress_record':{'id':str(uuid4()),'effective_on':'2026-10-25T10:30:00'}})
    assert audit_response(row)['before']['effective_on'] == '2026-10-25T10:30:00+08:00'


def test_missing_schema_blocks_edit_without_changing_record(progress_context, monkeypatch):
    from project_audit_models import ProjectOperationAudit
    db, _parent, (row, _status), client, _actor, _users = progress_context
    monkeypatch.setattr('annotation_progress_record_audit.edit_audit_ready', lambda _db: False)
    assert client.get('/annotation-ops/progress-record-capabilities').json() == {'edit_audit_ready': False}
    response = client.patch(f'/annotation-ops/status-history/{row.id}/progress',
        json={'effective_on':'2026-10-25T11:00:00+08:00','change_note':'不应保存'})
    assert response.status_code == 503
    db.refresh(row)
    assert row.change_note == '原始内容' and db.query(ProjectOperationAudit).count() == 0
