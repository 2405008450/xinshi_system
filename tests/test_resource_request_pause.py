"""暂停需求的状态机、日志与版本契约；不连接默认数据库。"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from concurrency import StaleUpdateError
from resource_request_schemas import ResourceRequestLifecycleAction, ResourceRequestPause, ResourceProgressLogResponse
import resource_request_service as service


def test_pause_contract_reason_and_required_version():
    version = '2026-10-15T10:20:30.123456+08:00'
    for reason in [None, '', '等' * 500]:
        assert ResourceRequestPause(expected_updated_at=version, reason=reason).reason == reason
    for payload in [{}, {'expected_updated_at': 'invalid'}, {'expected_updated_at': version, 'reason': '等' * 501}, {'expected_updated_at': version, 'changed_by': str(uuid4())}]:
        with pytest.raises(ValidationError):
            ResourceRequestPause(**payload)


@pytest.fixture
def state(monkeypatch):
    row = SimpleNamespace(id=uuid4(), demand_status='confirmed', request_status='in_progress',
                          progress_percent=35, owner_id=uuid4(), requested_at=datetime(2026, 10, 1, 12),
                          completed_at=None, updated_at=datetime(2026, 10, 15, 10, 20, 30, 123456))

    class Db:
        logs = []
        commits = 0

        def get(self, _model, key, **kwargs):
            assert kwargs == dict(with_for_update=True, populate_existing=True)
            return row if key == row.id else None

        def add(self, log): self.logs.append(log)
        def commit(self): self.commits += 1

    monkeypatch.setattr(service, 'get_resource_request', lambda *_: row)
    return row, Db()


def test_pause_resume_preserves_progress_and_records_reason_once(state):
    row, db = state
    actor = uuid4()
    original = (row.requested_at, row.owner_id, row.request_status, row.progress_percent, row.completed_at)
    pause = ResourceRequestPause(expected_updated_at=row.updated_at, reason='  等待客户  ')
    service.change_resource_request_pause(db, row.id, pause, actor)
    assert row.demand_status == 'paused'
    service.change_resource_request_pause(db, row.id, pause, actor)
    assert len(db.logs) == 1 and db.logs[0].changed_by == actor
    assert db.logs[0].progress_note == '资源需求已暂停；原因：等待客户'
    resume = ResourceRequestLifecycleAction(expected_updated_at=row.updated_at)
    service.change_resource_request_pause(db, row.id, resume, actor, resume=True)
    service.change_resource_request_pause(db, row.id, resume, actor, resume=True)
    assert row.demand_status == 'confirmed' and len(db.logs) == 2
    assert db.logs[-1].progress_note == '资源需求已恢复'
    assert original == (row.requested_at, row.owner_id, row.request_status, row.progress_percent, row.completed_at)
    log = ResourceProgressLogResponse.model_validate(dict(id=uuid4(), request_id=row.id, progress_percent=35, changed_at=db.logs[0].changed_at))
    assert log.model_dump(mode='json')['changed_at'].endswith('+08:00')


@pytest.mark.parametrize('demand,status,percent', [('draft', 'draft', 0), ('cancelled', 'cancelled', 35), ('confirmed', 'fulfilled', 100), ('confirmed', 'in_progress', 100)])
def test_pause_rejects_invalid_states(state, demand, status, percent):
    row, db = state
    row.demand_status, row.request_status, row.progress_percent = demand, status, percent
    with pytest.raises(HTTPException) as error:
        service.change_resource_request_pause(db, row.id, ResourceRequestPause(expected_updated_at=row.updated_at), None)
    assert error.value.status_code == 409 and not db.logs


def test_versions_preserve_precision_and_convert_real_instant(state):
    row, db = state
    version = row.updated_at.replace(tzinfo=timezone(timedelta(hours=8))).astimezone(timezone.utc)
    service._assert_request_version(row, version)
    with pytest.raises(StaleUpdateError):
        service.change_resource_request_pause(db, row.id, ResourceRequestPause(expected_updated_at=version - timedelta(microseconds=1)), None)
    assert not db.logs
    service.change_resource_request_pause(db, row.id, ResourceRequestPause(expected_updated_at=version), None)
    with pytest.raises(HTTPException):
        service.send_resource_request(db, row.id, None)
    with pytest.raises(HTTPException):
        service.update_resource_progress(db, row.id, SimpleNamespace(progress_percent=100), None)
    with pytest.raises(StaleUpdateError):
        service.change_resource_request_pause(db, row.id, ResourceRequestLifecycleAction(expected_updated_at=version), None, resume=True)
