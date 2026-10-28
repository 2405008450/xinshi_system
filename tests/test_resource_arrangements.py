"""每日安排回归；只在显式启用的隔离/局域网数据库中运行。"""
import os
from copy import deepcopy
from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from resource_development_schemas import ArrangementCellWrite, ArrangementCompletionWrite, ArrangementTargetWrite, ArrangementWrite


def test_target_validation_and_no_actor_spoofing():
    for payload in [dict(kind='request'), dict(kind='manual'), dict(kind='internal', language_id=uuid4()),
                    dict(kind='manual', language_id=uuid4(), request_id=uuid4())]:
        with pytest.raises(ValidationError):
            ArrangementTargetWrite(**payload)
    with pytest.raises(ValidationError):
        ArrangementCompletionWrite(revision=1, completed=True, completed_by=uuid4())
    platform = uuid4()
    with pytest.raises(ValidationError):
        ArrangementWrite(revision=0, cells=[dict(platform_id=platform), dict(platform_id=platform)])
    with pytest.raises(ValidationError):
        ArrangementCellWrite(platform_id=platform, operations={'edited': {'actor_name': '伪造'}})
    assert ArrangementCellWrite(platform_id=platform, owner_ids=[uuid4(), uuid4()]).owner_id is None
    duplicate = uuid4()
    with pytest.raises(ValidationError):
        ArrangementCellWrite(platform_id=platform, owner_ids=[duplicate, duplicate])
    project_id = uuid4()
    assert ArrangementTargetWrite(kind='recruitment_project', project_id=project_id).project_id == project_id
    with pytest.raises(ValidationError):
        ArrangementTargetWrite(kind='recruitment_project', project_id=project_id, request_id=uuid4())


def test_row_operation_history_edit_complete_reopen_reset_and_carry(db, context):
    from resource_arrangement_service import complete_arrangement, read_arrangement, arrangement_history, carry_preview
    from resource_development_models import DevelopmentAudit
    manager, owner, _, platforms, _ = context
    payload = dict(platform_id=platforms[0].id, owner_id=owner.id, role_tags=['客服'])
    day = save(db, context, cells=[payload])
    def row():
        db.flush()
        return read_arrangement(db, manager, day.work_date)['cells'][0]
    created = row()['operations']['created']
    assert created['actor_name'] == '统筹' and created['operated_at'].endswith('+08:00')
    original = row()['operations']['edited']
    count = db.query(DevelopmentAudit).count()
    save(db, context, revision=day.revision, cells=[payload])
    assert db.query(DevelopmentAudit).count() == count  # 原样保存不产生操作历史。
    complete_arrangement(db, owner, day.work_date, platforms[0].id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    assert row()['operations']['status']['actor_name'] == '负责人'
    assert row()['operations']['edited'] == original  # 勾选不覆盖内容修改人。
    complete_arrangement(db, manager, day.work_date, platforms[0].id, ArrangementCompletionWrite(revision=day.revision, completed=False))
    assert row()['completed_at'] is None
    assert row()['operations']['status']['action'] == 'reopen'
    complete_arrangement(db, owner, day.work_date, platforms[0].id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    save(db, context, revision=day.revision, cells=[payload | dict(role_tags=['译员'])])
    assert row()['operations']['status']['action'] == 'reset'
    save(db, context, user=owner, revision=day.revision, cells=[payload | dict(role_tags=['译员'], remarks='补充说明')])
    assert row()['operations']['status']['action'] == 'reset'  # 后续改备注仍保留重置证据。
    assert row()['operations']['edited']['actor_name'] == '负责人'
    manager.full_name = '统筹新名称'
    assert row()['operations']['created']['actor_name'] == '统筹'  # 新记录保存操作时的姓名。
    history = arrangement_history(db, day.work_date, platforms[0].id)
    assert history['total'] == 6
    assert history['items'][0]['changes'][0]['label'] == '账号备注'
    assert any(event['label'] == '安排变更，完成状态自动重置' for event in history['items'])
    assert all(event['operated_at'].endswith('+08:00') for event in history['items'])
    page = arrangement_history(db, day.work_date, platforms[0].id, skip=1, limit=2)
    assert page['items'] == history['items'][1:3] and page['total'] == history['total']
    draft = carry_preview(db, manager, date(2026, 10, 9))
    assert draft['cells'][0]['operations'] == {'created': None, 'edited': None, 'status': None}
    carried = save(db, context, day=date(2026, 10, 9), cells=[payload], carried_from=day.work_date)
    carried_event = read_arrangement(db, manager, carried.work_date)['cells'][0]['operations']['created']
    assert carried_event['label'] == '沿用安排' and carried_event['actor_name'] == '统筹新名称'
    assert carried_event['carried_from'] == day.work_date.isoformat()
    with pytest.raises(HTTPException) as error:
        arrangement_history(db, day.work_date, uuid4())
    assert error.value.status_code == 404


def test_operation_history_preserves_legacy_and_missing_evidence(db, context):
    from resource_arrangement_service import read_arrangement, arrangement_history
    from resource_development_models import DevelopmentAudit
    manager, owner, _, platforms, _ = context
    day = save(db, context, cells=[dict(platform_id=platforms[0].id, owner_id=owner.id)])
    cell = read_arrangement(db, manager, day.work_date)['cells'][0]
    entry = db.query(DevelopmentAudit).filter_by(entity_id=UUID(cell['id']), entity_type='arrangement_cell').one()
    entry.after = {key: value for key, value in entry.after.items() if key != '_operation'}
    assert arrangement_history(db, day.work_date, platforms[0].id)['items'][0]['actor_name'] == '统筹'
    db.delete(entry); db.flush()
    assert read_arrangement(db, manager, day.work_date)['cells'][0]['operations']['created'] is None
    assert arrangement_history(db, day.work_date, platforms[0].id) == {'items': [], 'total': 0}


def test_operation_people_are_isolated_per_account(db, context):
    from resource_arrangement_service import read_arrangement, complete_arrangement
    manager, owner, _, platforms, _ = context
    entries = [dict(platform_id=p.id, owner_id=owner.id, remarks='原备注') for p in platforms]
    day = save(db, context, cells=entries)
    save(db, context, user=owner, revision=day.revision, cells=[entries[0] | dict(remarks='负责人修改')])
    complete_arrangement(db, manager, day.work_date, platforms[1].id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    values = {row['platform_id']: row for row in read_arrangement(db, manager, day.work_date)['cells']}
    assert values[str(platforms[0].id)]['operations']['edited']['actor_name'] == '负责人'
    assert values[str(platforms[0].id)]['operations']['status'] is None
    assert values[str(platforms[1].id)]['operations']['edited']['actor_name'] == '统筹'
    assert values[str(platforms[1].id)]['operations']['status']['actor_name'] == '统筹'


def test_role_tag_normalization_and_limits():
    platform = uuid4()
    value = ArrangementCellWrite(platform_id=platform, role_tags=[' HR ', '', '客服', 'HR', '  '])
    assert value.role_tags == ['HR', '客服']
    assert 'role_tags' not in ArrangementCellWrite(platform_id=platform).model_fields_set
    assert 'role_tags' in ArrangementCellWrite(platform_id=platform, role_tags=[]).model_fields_set
    assert ArrangementCellWrite(platform_id=platform, role_tags=['岗' * 100]).role_tags == ['岗' * 100]
    for tags in [['岗' * 101], ['岗'] * 101, None, [123]]:
        with pytest.raises(ValidationError):
            ArrangementCellWrite(platform_id=platform, role_tags=tags)


def test_arrangement_business_clock_and_snapshot(monkeypatch):
    from datetime import datetime, timezone
    from types import SimpleNamespace
    import business_time
    from resource_development_models import DevelopmentArrangementCell
    from resource_development_service import snapshot

    class ServerUtcClock(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = datetime(2026, 10, 9, 9, 18, 43, 787825, tzinfo=timezone.utc)
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(business_time, 'datetime', ServerUtcClock)
    stored = business_time.business_now()
    assert stored == datetime(2026, 10, 9, 17, 18, 43, 787825) and stored.tzinfo is None
    assert business_time.business_iso(stored) == '2026-10-09T17:18:43.787825+08:00'
    assert business_time.business_iso(datetime(2026, 10, 9, 9, 18, 43, 787825, tzinfo=timezone.utc)) == business_time.business_iso(stored)
    table = DevelopmentArrangementCell.__table__
    cell = SimpleNamespace(__table__=table, __tablename__=table.name, **{column.name: None for column in table.columns})
    cell.completed_at = stored
    assert snapshot(cell)['completed_at'] == '2026-10-09T17:18:43.787825+08:00'
    assert cell.completed_at == stored


def test_roles_legacy_write_completion_reorder_and_partial_update(db, context):
    from resource_arrangement_service import complete_arrangement, get_cells, read_arrangement
    manager, owner, other, platforms, _ = context
    payload = dict(platform_id=platforms[0].id, owner_id=owner.id, role_tags=[' HR ', '客服', 'HR'])
    day = save(db, context, cells=[payload, dict(platform_id=platforms[1].id, owner_id=other.id, role_tags=['译员'])])
    complete_arrangement(db, owner, day.work_date, platforms[0].id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    first = next(c for c in get_cells(db, day) if c.platform_id == platforms[0].id)
    assert first.role_tags == ['HR', '客服'] and first.completed
    # 旧客户端只更新备注，不能意外清除岗位或完成信息。
    save(db, context, revision=day.revision, user=owner, cells=[dict(platform_id=platforms[0].id, owner_id=owner.id, remarks='补充备注')])
    assert first.role_tags == ['HR', '客服'] and first.completed
    save(db, context, revision=day.revision, user=owner, cells=[payload | dict(role_tags=['客服', 'HR'], remarks='补充备注')])
    assert first.completed and first.role_tags == ['客服', 'HR']
    save(db, context, revision=day.revision, user=owner, cells=[payload | dict(role_tags=['译员'])])
    assert not first.completed and first.completed_at is None and first.completed_by is None
    complete_arrangement(db, owner, day.work_date, platforms[0].id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    save(db, context, revision=day.revision, user=owner, cells=[payload | dict(role_tags=[])])
    assert first.role_tags == [] and not first.completed
    result = read_arrangement(db, manager, day.work_date)
    assert next(c for c in result['cells'] if c['platform_id'] == str(platforms[1].id))['role_tags'] == ['译员']


def test_role_only_carry_permissions_conflict_and_audit(db, context):
    from resource_arrangement_service import carry_preview, complete_arrangement, read_arrangement
    from resource_development_models import DevelopmentAudit
    manager, owner, other, platforms, _ = context
    payload = dict(platform_id=platforms[0].id, owner_id=owner.id, role_tags=['HR', '英语客服'])
    day = save(db, context, cells=[payload])
    assert read_arrangement(db, manager, day.work_date)['cells'][0]['targets'] == []
    complete_arrangement(db, owner, day.work_date, platforms[0].id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    revision = day.revision
    preview = carry_preview(db, manager, date(2026, 10, 9))
    assert preview['cells'][0]['role_tags'] == ['HR', '英语客服']
    assert not preview['cells'][0]['completed'] and preview['cells'][0]['completed_at'] is None
    assert read_arrangement(db, manager, date(2026, 10, 9))['revision'] == 0
    save(db, context, user=other, revision=day.revision, cells=[payload | dict(role_tags=['普通用户维护'])])
    save(db, context, user=owner, revision=day.revision, cells=[payload | dict(role_tags=['法语译员'])])
    with pytest.raises(HTTPException) as error:
        save(db, context, revision=revision, cells=[payload])
    assert error.value.status_code == 409
    changes = db.query(DevelopmentAudit).filter_by(entity_type='arrangement_cell').all()
    assert any(a.after.get('role_tags') == ['法语译员'] for a in changes)


@pytest.fixture
def db():
    if os.getenv('RUN_RESOURCE_DEVELOPMENT_DB_TESTS') != '1':
        pytest.skip('数据库回归需在局域网显式启用')
    import main  # noqa: F401
    from database import engine
    from sqlalchemy.orm import Session
    assert engine.url.host in {'localhost', '127.0.0.1', '192.168.31.144'}, '禁止连接生产数据库'
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode='create_savepoint')
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def context(db, monkeypatch):
    from models import AppUser
    from interpretation_models import InterpretationLanguage
    from resource_development_models import DevelopmentOption
    import resource_arrangement_service as service
    users = [AppUser(id=uuid4(), username='arrange_'+uuid4().hex, full_name=name,
                     password_hash='test-no-login', is_active=True) for name in ['统筹', '负责人', '其他人员']]
    platforms = [DevelopmentOption(id=uuid4(), kind='platform', category='national', name='测试平台'+uuid4().hex) for _ in range(2)]
    language = InterpretationLanguage(id=uuid4(), label='方言'+uuid4().hex, language_type='dialect', is_active=True)
    db.add_all([*users, *platforms, language]); db.flush()
    monkeypatch.setattr(service, 'can_delegate', lambda _db, user: user.id == users[0].id)
    return users[0], users[1], users[2], platforms, language


def request_context(db, context, status='confirmed', child=False):
    from annotation_models import AnnotationProject
    from resource_request_models import ResourceRequest, ResourceRequestItem
    _, _, _, _, language = context
    parent = AnnotationProject(id=uuid4(), order_no='AP-'+uuid4().hex, project_name='母项目')
    db.add(parent); db.flush()
    project = parent
    if child:
        project = AnnotationProject(id=uuid4(), order_no=parent.order_no+'-01', project_name='精确子订单',
                                    parent_project_id=parent.id, child_sequence_no=1)
        db.add(project); db.flush()
    request = ResourceRequest(id=uuid4(), request_no='RR-'+uuid4().hex, source_type='annotation', request_category='annotation_trial',
                              annotation_project_id=project.id, source_project_name_snapshot=project.project_name,
                              request_detail='需求', demand_status=status, request_status='draft' if status == 'draft' else 'submitted')
    request.items = [ResourceRequestItem(id=uuid4(), sequence_no=1, source_language_id=language.id, required_count=1)]
    db.add(request); db.flush()
    return request, project


def test_paused_request_preserves_arrangement_snapshots_and_carry_skips_it(db, context):
    from resource_arrangement_service import (arrangement_options, carry_preview, complete_arrangement,
                                             get_cells, list_arrangement_requests, read_arrangement)
    from resource_request_schemas import ResourceRequestPause, ResourceRequestLifecycleAction
    from resource_request_service import change_resource_request_pause
    manager, owner, _, platforms, language = context
    first, _ = request_context(db, context)
    second, _ = request_context(db, context)
    targets = [dict(kind='request', request_id=first.id, language_id=language.id),
               dict(kind='request_project', request_id=first.id),
               dict(kind='request', request_id=second.id, language_id=language.id),
               dict(kind='manual', language_id=language.id)]
    cell_payload = dict(platform_id=platforms[0].id, owner_id=owner.id, targets=targets)
    day = save(db, context, cells=[cell_payload])
    complete_arrangement(db, owner, day.work_date, platforms[0].id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    cell = get_cells(db, day)[0]
    before = (cell.targets.copy(), cell.completed_at, cell.completed_by, day.revision)
    change_resource_request_pause(db, first.id, ResourceRequestPause(expected_updated_at=first.updated_at), manager.id)
    visible = read_arrangement(db, manager, day.work_date)['cells'][0]
    assert [t['inactive_reason'] for t in visible['targets'][:2]] == ['需求已暂停'] * 2
    assert all(t['active'] for t in visible['targets'][2:])
    assert visible['completed'] and (cell.targets, cell.completed_at, cell.completed_by, day.revision) == before
    assert str(first.id) not in {r['id'] for r in list_arrangement_requests(db)['items']}
    assert all(t.get('request_id') != str(first.id) for t in arrangement_options(db)['targets'])
    # 已有失效项允许原样保留，不能新增到另一个账号。
    save(db, context, revision=day.revision, cells=[cell_payload])
    assert cell.completed
    with pytest.raises(HTTPException) as error:
        save(db, context, revision=day.revision, cells=[dict(platform_id=platforms[1].id, targets=[targets[1]])])
    assert error.value.status_code == 409 and '暂停' in error.value.detail
    preview = carry_preview(db, manager, date(2026, 10, 9))
    assert all(t.get('request_id') != str(first.id) for t in preview['cells'][0]['targets'])
    assert any('需求已暂停' in warning for warning in preview['warnings'])
    change_resource_request_pause(db, first.id, ResourceRequestLifecycleAction(expected_updated_at=first.updated_at), manager.id, resume=True)
    assert all(t['active'] for t in read_arrangement(db, manager, day.work_date)['cells'][0]['targets'])
    assert cell.completed and cell.completed_at == before[1]
    assert str(first.id) in {r['id'] for r in list_arrangement_requests(db)['items']}


def test_pause_migration_repeated_and_legacy_migrations_preserve_paused_rows(db, context):
    from pathlib import Path
    from main import RESOURCE_REQUEST_LIFECYCLE_STATEMENTS
    from sqlalchemy import text
    request, _ = request_context(db, context)
    db.execute(text('ALTER TABLE resource_request DROP CONSTRAINT ck_resource_request_demand_status'))
    db.execute(text("ALTER TABLE resource_request ADD CONSTRAINT ck_resource_request_demand_status CHECK(demand_status IN ('draft','confirmed','cancelled'))"))
    migration = Path('data/migrations/20261015_resource_request_pause.sql').read_text(encoding='utf-8')
    db.connection().exec_driver_sql(migration)
    request.demand_status = 'paused'; db.flush()
    before = (request.request_status, request.updated_at, request.progress_percent)
    db.connection().exec_driver_sql(migration)
    db.connection().exec_driver_sql(Path('data/migrations/20260909_add_resource_request_lifecycle.sql').read_text(encoding='utf-8'))
    for statement in RESOURCE_REQUEST_LIFECYCLE_STATEMENTS:
        db.execute(text(statement))
    db.refresh(request)
    assert request.demand_status == 'paused'
    assert (request.request_status, request.updated_at, request.progress_percent) == before


def test_pause_http_permissions_versions_edit_guards_and_cancel(db, context, monkeypatch):
    import json
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    import routers.auth as auth
    from routers.resource_requests import router
    from concurrency import StaleUpdateError
    from resource_request_models import ResourceRequestProgressLog
    manager, *_ = context
    request, _ = request_context(db, context)
    request.progress_percent = 35; request.request_status = 'in_progress'; db.flush()
    permissions = ['projects:read', 'projects:write']
    monkeypatch.setattr(auth, 'get_user_permission_codes', lambda *_: permissions)
    monkeypatch.setattr(auth, 'user_has_permission', lambda _db, _user, code: code in permissions)
    app = FastAPI(); app.include_router(router)
    app.add_exception_handler(StaleUpdateError, lambda _req, exc: JSONResponse(status_code=409, content={'detail': str(exc)}))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: manager
    path = f'/resource-requests/{request.id}'
    with TestClient(app) as client:
        detail = client.get(path)
        assert detail.status_code == 200, detail.text
        original = detail.json()
        version = {'expected_updated_at': original['updated_at']}
        permissions.remove('projects:write')
        assert client.post(path + '/pause', json=version).status_code == 403
        assert client.post(path + '/resume', json=version).status_code == 403
        permissions.append('projects:write')
        assert client.post(path + '/pause', json={}).status_code == 422
        assert client.post(path + '/pause', json=version | {'reason': '等' * 501}).status_code == 422
        paused = client.post(path + '/pause', json=version | {'reason': '等待客户'})
        assert paused.status_code == 200, paused.text
        paused = paused.json()
        assert paused['demand_status'] == 'paused' and paused['updated_at'].endswith('+08:00')
        filters = {'field_filters': json.dumps({'demand_status': {'op': 'in', 'value': ['paused']}})}
        page = client.get('/resource-requests/page', params=filters)
        assert page.status_code == 200, page.text
        assert page.json()['total'] == 1 and page.json()['items'][0]['id'] == str(request.id)
        assert client.get('/resource-requests/count', params=filters).json()['total'] == page.json()['total']
        assert client.post(path + '/pause', json=version).status_code == 200
        assert client.post(path + '/send').status_code == 409
        assert client.patch(path + '/progress', json={'progress_percent': 100}).status_code == 409
        assert client.put(path, json=original | version).status_code == 409
        assert client.put(path, json=paused | {'request_status': 'fulfilled'}).status_code == 409
        # 暂停期间正常编辑不改变生命周期；新版本可用于恢复，旧版本应拒绝。
        edited = client.put(path, json=paused | {'request_detail': '暂停期间补充需求', 'expected_updated_at': paused['updated_at']})
        assert edited.status_code == 200, edited.text
        assert edited.json()['demand_status'] == 'paused'
        assert client.post(path + '/resume', json=version).status_code == 409
        resumed = client.post(path + '/resume', json={'expected_updated_at': edited.json()['updated_at']})
        assert resumed.status_code == 200, resumed.text
        for field in ['progress_percent', 'requested_at', 'request_status', 'owner_id', 'completed_at']:
            assert resumed.json()[field] == original[field]
        assert client.post(path + '/resume', json=version).status_code == 200
        paused_again = client.post(path + '/pause', json={'expected_updated_at': resumed.json()['updated_at']})
        assert paused_again.status_code == 200
        cancelled = client.post(path + '/cancel')
        assert cancelled.status_code == 200 and cancelled.json()['demand_status'] == 'cancelled'
        assert client.post(path + '/resume', json={'expected_updated_at': cancelled.json()['updated_at']}).status_code == 409
        assert client.post('/resource-requests/' + str(uuid4()) + '/pause', json=version).status_code == 404
        logs = client.get(path + '/progress-logs').json()
        assert all(log['changed_at'].endswith('+08:00') for log in logs)
        assert sum('已暂停' in (log.progress_note or '') for log in db.query(ResourceRequestProgressLog).filter_by(request_id=request.id)) == 2


def test_concurrent_pause_retries_record_one_log(db):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy.orm import Session
    from database import engine
    from resource_request_models import ResourceRequest, ResourceRequestProgressLog
    from resource_request_schemas import ResourceRequestPause
    from resource_request_service import change_resource_request_pause
    from business_time import business_now
    # 此测试仅在 fixture 已确认的隔离数据库内使用独立事务，才能验证真实行锁。
    request_id = uuid4()
    with Session(engine) as session:
        row = ResourceRequest(id=request_id, request_no='RR-concurrency-' + uuid4().hex, source_type='other',
                              request_category='other', other_source_name='并发测试', source_project_name_snapshot='并发测试',
                              request_detail='', demand_status='confirmed', request_status='submitted', updated_at=business_now())
        session.add(row); session.commit(); version = row.updated_at
    try:
        def pause():
            with Session(engine) as session:
                return change_resource_request_pause(session, request_id, ResourceRequestPause(expected_updated_at=version), None)['demand_status']
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(lambda _: pause(), range(2))) == ['paused', 'paused']
        with Session(engine) as session:
            assert session.query(ResourceRequestProgressLog).filter_by(request_id=request_id).count() == 1
    finally:
        with Session(engine) as session:
            session.delete(session.get(ResourceRequest, request_id)); session.commit()


def save(db, context, revision=0, cells=None, day=date(2026, 10, 8), user=None, **kwargs):
    from resource_arrangement_service import save_arrangement
    manager, owner, _, platforms, _ = context
    if cells is None:
        cells = [dict(platform_id=platforms[0].id, owner_id=owner.id, remarks='账号备注')]
    return save_arrangement(db, user or manager, day, ArrangementWrite(revision=revision, cells=cells, **kwargs))


def test_multi_owners_share_one_completion_and_authorization(db, context):
    from resource_arrangement_service import complete_arrangement, read_arrangement, carry_preview
    from models import AppUser
    from resource_development_models import DevelopmentAudit
    manager, first, second, platforms, _ = context
    outsider = AppUser(id=uuid4(), username='outsider_'+uuid4().hex, full_name='无关人员',
                      password_hash='test-no-login', is_active=True)
    db.add(outsider); db.flush()
    day = save(db, context, cells=[dict(platform_id=platforms[0].id, owner_ids=[first.id, second.id])])
    row = read_arrangement(db, first, day.work_date)['cells'][0]
    assert row['owner_ids'] == [str(first.id), str(second.id)]
    assert row['owner_name'] == '负责人、其他人员' and row['can_complete']
    assert read_arrangement(db, manager, day.work_date)['cells'][0]['can_complete']
    assert not read_arrangement(db, outsider, day.work_date)['cells'][0]['can_complete']
    with pytest.raises(HTTPException) as error:
        complete_arrangement(db, outsider, day.work_date, platforms[0].id,
                             ArrangementCompletionWrite(revision=day.revision, completed=True))
    assert error.value.status_code == 403
    complete_arrangement(db, second, day.work_date, platforms[0].id,
                         ArrangementCompletionWrite(revision=day.revision, completed=True))
    row = read_arrangement(db, first, day.work_date)['cells'][0]
    assert row['completed'] and row['completed_by_name'] == '其他人员'
    save(db, context, revision=day.revision,
         cells=[dict(platform_id=platforms[0].id, owner_ids=[second.id, first.id])])
    assert read_arrangement(db, first, day.work_date)['cells'][0]['completed']
    save(db, context, revision=day.revision,
         cells=[dict(platform_id=platforms[0].id, owner_ids=[first.id])])
    assert not read_arrangement(db, first, day.work_date)['cells'][0]['completed']
    assert any(a.before.get('owners') != a.after.get('owners') for a in
               db.query(DevelopmentAudit).filter_by(entity_type='arrangement_cell').all())
    assert carry_preview(db, manager, date(2026, 10, 9))['cells'][0]['owner_ids'] == [str(first.id)]


def test_recruitment_project_direction_search_deduplicate_and_expire(db, context):
    from recruitment_models import RecruitmentProject
    from resource_arrangement_service import arrangement_options, read_arrangement, carry_preview
    manager, owner, _, platforms, _ = context
    project = RecruitmentProject(id=uuid4(), order_no='RP-UNIQUE-' + uuid4().hex,
                                 project_name='全职招聘测试', project_status='sourcing')
    db.add(project); db.flush()
    candidates = arrangement_options(db, recruitment_keyword=project.order_no)['recruitment_projects']
    assert [candidate['project_id'] for candidate in candidates] == [str(project.id)]
    day = save(db, context, cells=[dict(platform_id=platforms[0].id, owner_ids=[owner.id],
        targets=[dict(kind='recruitment_project', project_id=project.id)],
        projects=[dict(source_type='recruitment', project_id=project.id)])])
    row = read_arrangement(db, manager, day.work_date)['cells'][0]
    assert len(row['projects']) == 1 and row['manual_projects'] == []
    assert row['targets'][0]['project']['project_id'] == str(project.id)
    project.project_status = 'closed'; db.flush()
    assert arrangement_options(db, recruitment_keyword=project.order_no)['recruitment_projects'] == []
    row = read_arrangement(db, manager, day.work_date)['cells'][0]
    assert row['targets'][0]['active'] is False
    assert carry_preview(db, manager, date(2026, 10, 9))['cells'][0]['targets'] == []


def test_read_blank_is_read_only_and_ranges(db, context):
    from resource_arrangement_service import read_arrangement, list_arrangements
    from resource_development_models import DevelopmentArrangement
    manager, *_ = context
    result = read_arrangement(db, manager, date(2026, 10, 8))
    assert result['revision'] == 0 and result['cells'] == []
    assert db.query(DevelopmentArrangement).count() == 0
    save(db, context)
    assert list_arrangements(db, manager, date(2026, 10, 9), date(2026, 10, 10))['total'] == 0
    assert list_arrangements(db, manager, date(2026, 10, 8), date(2026, 10, 8))['total'] == 1
    with pytest.raises(HTTPException) as error:
        list_arrangements(db, manager, date(2026, 10, 9), date(2026, 10, 8))
    assert error.value.status_code == 422


def test_candidates_cancel_resend_language_adjustment_and_child(db, context):
    from resource_arrangement_service import arrangement_options, read_arrangement
    manager, owner, _, platforms, language = context
    first, child = request_context(db, context, child=True)
    second, _ = request_context(db, context)
    draft, _ = request_context(db, context, status='draft')
    targets = arrangement_options(db)['targets']
    assert {t['request_id'] for t in targets} == {str(first.id),str(second.id)}
    target = next(t for t in targets if t['request_id'] == str(first.id))
    assert target['project']['project_id'] == str(child.id) and target['project']['parent_project_id']
    payload = dict(platform_id=platforms[0].id, owner_id=owner.id,
                   targets=[dict(kind='request', request_id=first.id, language_id=language.id), dict(kind='manual', language_id=language.id), dict(kind='internal')])
    day = save(db, context, cells=[payload])
    first.demand_status, first.request_status = 'cancelled', 'cancelled'; db.flush()
    assert {t['request_id'] for t in arrangement_options(db)['targets']} == {str(second.id)}
    row = read_arrangement(db, manager, day.work_date)['cells'][0]
    assert row['targets'][0]['inactive_reason'] == '需求已取消'
    assert row['projects'][0]['project_id'] == str(child.id)
    # 原有失效项可保存，不允许另一个账号新选取消的需求。
    save(db, context, revision=day.revision, cells=[payload])
    with pytest.raises(HTTPException) as error:
        save(db, context, revision=day.revision, cells=[payload | {'platform_id':platforms[1].id}])
    assert error.value.status_code == 409
    first.demand_status, first.request_status = 'confirmed', 'submitted'; db.flush()
    assert str(first.id) in {t['request_id'] for t in arrangement_options(db)['targets']}
    first.items[0].source_language_id = None; db.flush(); db.expire(first, ['items'])
    assert read_arrangement(db, manager, day.work_date)['cells'][0]['targets'][0]['inactive_reason'] == '需求语种已调整'
    assert str(draft.id) not in {t['request_id'] for t in arrangement_options(db)['targets']}


def test_partial_update_permissions_completion_and_revision(db, context):
    from resource_arrangement_service import complete_arrangement, get_cells
    manager, owner, other, platforms, _ = context
    day = save(db, context, cells=[dict(platform_id=p.id, owner_id=u.id) for p,u in zip(platforms,[owner,other])], remarks='每日备注')
    complete_arrangement(db, manager, day.work_date, platforms[0].id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    cells = get_cells(db, day)
    first = next(c for c in cells if c.platform_id == platforms[0].id)
    assert first.completed_by == manager.id and first.completed_by != first.owner_id and first.completed_at
    save(db, context, revision=day.revision, user=owner, cells=[dict(platform_id=platforms[0].id, owner_id=owner.id, remarks='本人修改')])
    assert first.completed  # 仅修改备注不会重置完成。
    assert len(get_cells(db, day)) == 2 and day.remarks == '每日备注'
    for user,cells,remarks in [(owner,[dict(platform_id=platforms[1].id,owner_id=other.id)],None),
                               (owner,[dict(platform_id=platforms[0].id,owner_id=other.id)],None),
                               (owner,[], '越权每日备注')]:
        save(db,context,revision=day.revision,user=user,cells=cells,remarks=remarks)
    old_revision = day.revision
    save(db, context, revision=day.revision, cells=[dict(platform_id=platforms[0].id,owner_id=other.id, role_tags=['更新岗位'])])
    assert not first.completed and not first.completed_by and not first.completed_at
    with pytest.raises(HTTPException) as error:
        save(db, context, revision=old_revision)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        complete_arrangement(db,owner,day.work_date,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=True))
    assert error.value.status_code == 403
    complete_arrangement(db,other,day.work_date,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=True))


def test_carry_nearest_weekend_skip_invalid_and_no_persistence(db, context):
    from resource_arrangement_service import carry_preview, complete_arrangement, get_cells
    from resource_development_models import DevelopmentArrangement
    manager, owner, _, platforms, language = context
    request, _ = request_context(db,context)
    friday=date(2026,10,9); monday=date(2026,10,12)
    day=save(db,context,day=friday,remarks='沿用备注',cells=[dict(platform_id=platforms[0].id,owner_id=owner.id,
        targets=[dict(kind='request',request_id=request.id,language_id=language.id),dict(kind='manual',language_id=language.id)],remarks='账号备注')])
    complete_arrangement(db,manager,friday,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=True))
    owner.is_active=False; request.demand_status='cancelled'; db.flush()
    preview=carry_preview(db,manager,monday)
    assert preview['carried_from']==friday.isoformat() and preview['remarks']=='沿用备注'
    assert preview['cells'][0]['owner_id'] is None and not preview['cells'][0]['completed']
    assert preview['cells'][0]['completed_at'] is None and len(preview['warnings'])==2
    assert [t['kind'] for t in preview['cells'][0]['targets']]==['manual']
    assert db.query(DevelopmentArrangement).count()==1
    save(db,context,day=monday,cells=[],carried_from=friday)
    with pytest.raises(HTTPException) as error:
        carry_preview(db,manager,monday)
    assert error.value.status_code==409
    assert get_cells(db,day)[0].completed


def test_unassigned_cannot_complete_and_name_snapshots(db,context):
    from resource_arrangement_service import complete_arrangement,read_arrangement
    manager,owner,_,platforms,language=context
    day=save(db,context,cells=[dict(platform_id=platforms[0].id,owner_id=None,targets=[dict(kind='manual',language_id=language.id)])])
    with pytest.raises(HTTPException) as error:
        complete_arrangement(db,manager,day.work_date,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=True))
    assert error.value.status_code==422
    old_platform,old_language=platforms[0].name,language.label
    platforms[0].name='平台更名'; language.label='方言更名'; db.flush()
    cell=read_arrangement(db,manager,day.work_date)['cells'][0]
    assert cell['platform_name']==old_platform and cell['targets'][0]['label']==old_language


def test_empty_carry_and_unprivileged_create(db,context):
    from resource_arrangement_service import carry_preview
    manager,owner,*_=context
    with pytest.raises(HTTPException) as error:
        carry_preview(db,manager,date(2026,10,8))
    assert error.value.status_code==404
    assert save(db,context,user=owner).revision == 1


def test_stopped_language_candidates_and_carry(db,context):
    from resource_arrangement_service import arrangement_options,carry_preview,read_arrangement
    manager,owner,_,platforms,language=context
    request,_=request_context(db,context)
    day=save(db,context,cells=[dict(platform_id=platforms[0].id,owner_id=owner.id,
        targets=[dict(kind='request',request_id=request.id,language_id=language.id)])])
    language.is_active=False; db.flush()
    assert arrangement_options(db)['targets']==[]
    assert read_arrangement(db,manager,day.work_date)['cells'][0]['targets'][0]['inactive_reason']=='语种已停用'
    preview=carry_preview(db,manager,date(2026,10,9))
    assert preview['cells'][0]['targets']==[] and preview['warnings']


def test_all_request_language_positions_are_candidates(db,context):
    from interpretation_models import InterpretationLanguage
    from resource_request_models import ResourceRequestItemExtraLanguage
    from resource_arrangement_service import arrangement_options
    request,_=request_context(db,context)
    extras=[InterpretationLanguage(id=uuid4(),label='多语种'+uuid4().hex,language_type='language',is_active=True) for _ in range(3)]
    db.add_all(extras);db.flush()
    request.items[0].target_language_id=extras[0].id
    request.items[0].extra_languages=[ResourceRequestItemExtraLanguage(sequence_no=i,language_id=l.id) for i,l in enumerate(extras[1:],start=3)]
    db.flush();db.expire(request,['items'])
    assert {t['language_id'] for t in arrangement_options(db)['targets']}=={str(context[4].id),*(str(l.id) for l in extras)}


def test_manual_projects_and_completion_reopen(db,context):
    from resource_arrangement_service import complete_arrangement,get_cells,read_arrangement
    manager,owner,_,platforms,_=context
    _,project=request_context(db,context,child=True)
    cell=dict(platform_id=platforms[0].id,owner_id=owner.id,projects=[dict(source_type='annotation',project_id=project.id)])
    day=save(db,context,cells=[cell])
    complete_arrangement(db,owner,day.work_date,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=True))
    assert get_cells(db,day)[0].completed_by==owner.id
    complete_arrangement(db,manager,day.work_date,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=False))
    assert not get_cells(db,day)[0].completed_at
    read=read_arrangement(db,manager,day.work_date)['cells'][0]
    assert read['manual_projects'][0]['project_id']==str(project.id)
    complete_arrangement(db,owner,day.work_date,platforms[0].id,ArrangementCompletionWrite(revision=day.revision,completed=True))
    save(db,context,revision=day.revision,cells=[cell | {'projects':[]}])
    assert not get_cells(db,day)[0].completed


def test_http_routes_permissions_and_incremental_save(db,context,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    import routers.auth as auth
    from routers.resource_development import router
    manager,owner,other,platforms,_=context
    current={'user':manager,'codes':['talents:read','talents:write']}
    monkeypatch.setattr(auth,'get_user_permission_codes',lambda *_:current['codes'])
    app=FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:current['user']
    with TestClient(app) as client:
        path='/resource-development/arrangements/2026-10-08'
        assert client.get(path).json()['revision']==0
        created=client.put(path,json={'revision':0,'cells':[{'platform_id':str(platforms[0].id),'owner_id':str(owner.id)}]})
        assert created.status_code==200,created.text
        current.update(user=owner,codes=['talents:read'])
        assert client.get(path).status_code==200
        assert client.patch(path+f'/cells/{platforms[0].id}/completion',json={'revision':1,'completed':True}).status_code==200
        current['codes'].append('talents:write')
        complete=client.patch(path+f'/cells/{platforms[0].id}/completion',json={'revision':2,'completed':True})
        assert complete.status_code==200,complete.text
        assert complete.json()['cells'][0]['completed_by']==str(owner.id)
        assert complete.json()['cells'][0]['completed_at'].endswith('+08:00')
        assert complete.json()['updated_at'].endswith('+08:00')
        history_path = path + f'/cells/{platforms[0].id}/history'
        history = client.get(history_path)
        assert history.status_code == 200 and history.json()['total'] == 2
        assert history.json()['items'][0]['actor_name'] == '负责人'
        assert history.json()['items'][0]['operated_at'].endswith('+08:00')
        assert client.get(history_path, params={'limit': 1}).json()['items'] == history.json()['items'][:1]
        assert client.get(history_path, params={'limit': 101}).status_code == 422
        assert client.get(path + f'/cells/{uuid4()}/history').status_code == 404
        assert client.put(path,json={'revision':1,'cells':[]}).status_code==409
        assert client.put(path,json={'revision':2,'cells':[{'platform_id':str(platforms[0].id),'owner_id':str(other.id)}]}).status_code==200
        current['codes']=[]
        assert client.get(path).status_code==200
        assert client.get(history_path).status_code == 200


def assign(db, context, request, accounts, revision=0, day=date(2026, 10, 12), user=None):
    from resource_arrangement_service import assign_request
    from resource_development_schemas import RequestArrangementWrite
    return assign_request(db, user or context[0], request.id, day,
                          RequestArrangementWrite(revision=revision, platform_ids=accounts))


def test_request_batch_assignment_preserves_other_work_and_is_idempotent(db, context):
    from resource_arrangement_service import get_cells, list_arrangement_requests, arrangement_request_detail, read_arrangement
    manager, owner, _, platforms, language = context
    request, project = request_context(db, context, child=True)
    other_request, _ = request_context(db, context)
    day = save(db, context, day=date(2026, 10, 12), remarks='每日备注', cells=[{
        'platform_id': platforms[0].id, 'owner_id': owner.id, 'role_tags': ['HR'], 'remarks': '账号备注',
        'projects': [{'source_type': 'annotation', 'project_id': project.id}],
        'targets': [{'kind': 'request', 'request_id': other_request.id, 'language_id': language.id}],
    }])
    day = assign(db, context, request, [p.id for p in platforms], day.revision)
    first = next(c for c in get_cells(db, day) if c.platform_id == platforms[0].id)
    assert first.owner_id == owner.id and first.role_tags == ['HR'] and first.remarks == '账号备注'
    assert first.projects[0]['project_id'] == str(project.id) and day.remarks == '每日备注'
    assert len(first.targets) == 2
    version = day.revision
    day = assign(db, context, request, [p.id for p in platforms], version)
    assert day.revision == version
    assert len(arrangement_request_detail(db, request.id)['arrangements']) == 2
    assert len(list_arrangement_requests(db, keyword=project.order_no)['items']) == 1
    assert list_arrangement_requests(db, keyword='精确子订单')['items'][0]['id'] == str(request.id)
    rendered = read_arrangement(db, manager, day.work_date)
    assert all(any(p['project_id'] == str(project.id) for p in c['projects']) for c in rendered['cells'])
    day = assign(db, context, request, [platforms[1].id], day.revision)
    assert len(first.targets) == 1 and first.targets[0]['request_id'] == str(other_request.id)
    assert first.projects[0]['project_id'] == str(project.id)
    assert len(arrangement_request_detail(db, request.id)['arrangements']) == 1


def test_request_without_language_and_multiple_requests_for_same_project(db, context):
    from resource_arrangement_service import get_cells, arrangement_request_detail, carry_preview
    from resource_request_models import ResourceRequest
    request, project = request_context(db, context)
    request.items = []
    second = ResourceRequest(id=uuid4(), request_no='RR-'+uuid4().hex, source_type='annotation',
                             request_category='annotation_formal', annotation_project_id=project.id,
                             source_project_name_snapshot=project.project_name,
                             request_detail='无语种项目需求', demand_status='confirmed', request_status='submitted')
    db.add(second); db.flush()
    account = context[3][0].id
    day = assign(db, context, request, [account])
    day = assign(db, context, second, [account], day.revision)
    assert len(get_cells(db, day)[0].targets) == 2
    day = assign(db, context, request, [], day.revision)
    assert get_cells(db, day)[0].targets[0]['request_id'] == str(second.id)
    assert arrangement_request_detail(db, request.id)['arrangements'] == []
    preview = carry_preview(db, context[0], date(2026, 10, 13))
    assert preview['cells'][0]['targets'][0]['request_id'] == str(second.id)
    second.demand_status = 'cancelled'; db.flush()
    detail = arrangement_request_detail(db, second.id)
    assert detail['arrangements'][0]['active'] is False
    assert carry_preview(db, context[0], date(2026, 10, 13))['cells'][0]['targets'] == []


def test_request_assignment_permissions_conflicts_and_cancelled(db, context):
    request, _ = request_context(db, context)
    account = context[3][0].id
    day = assign(db, context, request, [account], user=context[1])
    with pytest.raises(HTTPException) as error:
        assign(db, context, request, [], 0)
    assert error.value.status_code == 409
    request.demand_status = 'cancelled'; db.flush()
    with pytest.raises(HTTPException) as error:
        assign(db, context, request, [account], day.revision)
    assert error.value.status_code == 409


def test_request_list_pagination_drafts_and_live_project_names(db, context):
    from resource_arrangement_service import list_arrangement_requests
    values = [request_context(db, context) for _ in range(7)]
    draft, _ = request_context(db, context, status='draft')
    values[0][0].demand_status = 'cancelled'
    values[1][1].project_name = '新名称专用关键字'; db.flush()
    page = list_arrangement_requests(db)
    assert page['total'] == 6 and len(page['items']) == 5
    following = list_arrangement_requests(db, skip=5)
    assert len(following['items']) == 1
    assert set(r['id'] for r in page['items']).isdisjoint(r['id'] for r in following['items'])
    assert list_arrangement_requests(db, keyword='新名称专用关键字')['total'] == 1
    assert list_arrangement_requests(db, keyword=draft.request_no)['total'] == 0


def test_request_assignment_resets_completion_and_preserves_it_on_repeat(db, context):
    from resource_arrangement_service import complete_arrangement, get_cells
    request, _ = request_context(db, context)
    platform = context[3][0]
    day = save(db, context, day=date(2026, 10, 12), cells=[dict(platform_id=platform.id, owner_id=context[1].id)])
    complete_arrangement(db, context[1], day.work_date, platform.id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    day = assign(db, context, request, [platform.id], day.revision)
    assert not get_cells(db, day)[0].completed
    complete_arrangement(db, context[1], day.work_date, platform.id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    revision = day.revision
    assign(db, context, request, [platform.id], revision)
    assert get_cells(db, day)[0].completed and day.revision == revision


def test_request_assignment_http_and_snapshot_validation(db, context, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.resource_development import router
    import routers.auth as auth
    request, _ = request_context(db, context)
    codes = ['talents:read', 'talents:write']
    monkeypatch.setattr(auth, 'get_user_permission_codes', lambda *_: codes)
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: context[0]
    with TestClient(app) as client:
        base = '/resource-development/arrangement-requests'
        assert client.get(base).json()['total'] == 1
        path = f'{base}/{request.id}/dates/2026-10-12'
        payload = dict(revision=0, platform_ids=[str(p.id) for p in context[3]])
        assert client.put(path, json=payload | {'project_name': '伪造快照'}).status_code == 422
        assert client.put(path, json=payload | {'platform_ids': payload['platform_ids'] * 2}).status_code == 422
        response = client.put(path, json=payload)
        assert response.status_code == 200, response.text
        assert response.json()['updated_at'].endswith('+08:00')
        assert len(client.get(f'{base}/{request.id}').json()['arrangements']) == 2
        codes.remove('talents:write')
        assert client.put(path, json=payload).status_code == 409


def test_sent_project_request_enters_arrangement_queue(db, context):
    from resource_arrangement_service import list_arrangement_requests, arrangement_request_detail
    from resource_request_service import send_resource_request
    request, project = request_context(db, context, status='draft', child=True)
    assert list_arrangement_requests(db)['total'] == 0
    send_resource_request(db, request.id, context[0].id)
    row = list_arrangement_requests(db)['items'][0]
    assert row['id'] == str(request.id) and row['order_no'] == project.order_no
    assign(db, context, request, [p.id for p in context[3]])
    assert len(arrangement_request_detail(db, request.id)['arrangements']) == 2


def scoped_request(db, context):
    from annotation_models import AnnotationProjectLanguageItem
    from interpretation_models import InterpretationLanguage
    request, project = request_context(db, context)
    second = InterpretationLanguage(id=uuid4(), label='普通话' + uuid4().hex, language_type='language', is_active=True)
    db.add(second); db.flush()
    project.language_items = [
        AnnotationProjectLanguageItem(id=uuid4(), sequence_no=1, source_language_id=context[4].id,
                                      regions=[{'city': '广州', 'district': '天河', 'street': ''}, {'city': '深圳'}]),
        AnnotationProjectLanguageItem(id=uuid4(), sequence_no=2, source_language_id=second.id, regions=[{'city': '北京'}]),
    ]
    db.flush()
    return request, project


def test_project_options_child_languages_are_independent_and_searchable(db, context):
    from annotation_models import AnnotationProject, AnnotationProjectLanguageItem
    from interpretation_models import InterpretationLanguage
    from resource_arrangement_service import arrangement_project_options
    _, parent = scoped_request(db, context)
    language = InterpretationLanguage(id=uuid4(), label='闽南方言' + uuid4().hex, language_type='dialect', is_active=True)
    db.add(language); db.flush()
    child = AnnotationProject(id=uuid4(), order_no=parent.order_no + '-01', project_name=parent.project_name,
                              parent_project_id=parent.id, child_sequence_no=1)
    child.language_items = [AnnotationProjectLanguageItem(id=uuid4(), sequence_no=1, source_language_id=language.id, regions=[])]
    db.add(child); db.flush()
    options = {item['project_id']: item for item in arrangement_project_options(db, 'annotation')}
    assert options[str(child.id)]['languages'] == [language.label]
    assert language.label not in options[str(parent.id)]['languages']
    assert len(options[str(parent.id)]['languages']) == 2
    assert options[str(child.id)]['parent_project_id'] == str(parent.id)
    assert options[str(parent.id)]['parent_project_id'] == ''
    found = arrangement_project_options(db, 'annotation', keyword=language.label)
    assert [item['project_id'] for item in found] == [str(child.id)]
    assert arrangement_project_options(db, 'annotation', keyword=child.order_no)[0]['project_id'] == str(child.id)
    child.language_items = []; db.flush()
    empty = arrangement_project_options(db, 'annotation', keyword=child.order_no)[0]
    assert empty['languages'] == []  # 不从名称或母订单补猜语种。


def test_direction_candidates_only_confirmed_but_history_is_preserved(db, context):
    from resource_arrangement_service import arrangement_options, read_arrangement
    confirmed, _ = request_context(db, context)
    paused, _ = request_context(db, context)
    day = assign(db, context, paused, [context[3][0].id])
    paused.demand_status = 'paused'
    request_context(db, context, status='draft')
    request_context(db, context, status='cancelled')
    db.flush()
    options = arrangement_options(db)
    for group in ['targets', 'request_projects']:
        assert {item['request_id'] for item in options[group]} == {str(confirmed.id)}
        assert all(item['demand_status'] == 'confirmed' for item in options[group])
    history = read_arrangement(db, context[0], day.work_date)['cells'][0]['targets']
    assert history[0]['request_id'] == str(paused.id) and history[0]['active'] is False


def test_project_options_language_directions_and_translation_text(db, context):
    from interpretation_models import InterpretationLanguage, InterpretationProject, InterpretationProjectLanguageDirection
    from recruitment_models import RecruitmentProject, RecruitmentProjectLanguageDirection
    from models import TranslationProject
    from resource_arrangement_service import arrangement_project_options
    language = context[4]
    second = InterpretationLanguage(id=uuid4(), label='英语' + uuid4().hex, language_type='language', is_active=True)
    db.add(second); db.flush()
    interpretation = InterpretationProject(id=uuid4(), order_no='IP-QA-' + uuid4().hex, project_name='口译候选')
    interpretation.language_directions = [InterpretationProjectLanguageDirection(id=uuid4(), sequence_no=1, source_language_id=language.id, target_language_id=second.id)]
    recruitment = RecruitmentProject(id=uuid4(), order_no='RP-QA-' + uuid4().hex, project_name='招聘候选')
    recruitment.language_directions = [RecruitmentProjectLanguageDirection(id=uuid4(), sequence_no=1, direction_type='translation', source_language_id=language.id, target_language_id=second.id)]
    translation = TranslationProject(id=uuid4(), order_no='TP-QA-' + uuid4().hex, project_name='笔译候选', language_pair='中文→英语；英语→日语')
    db.add_all([interpretation, recruitment, translation]); db.flush()
    for kind in ['interpretation', 'recruitment']:
        assert arrangement_project_options(db, kind, language.label)[0]['languages'] == [language.label + ' → ' + second.label]
    assert arrangement_project_options(db, 'translation', '日语')[0]['languages'] == ['中文→英语', '英语→日语']


def test_scope_combinations_stable_read_only_and_project_fallback(db, context):
    from resource_arrangement_service import request_scope_options, arrangement_request_detail
    request, project = scoped_request(db, context)
    before = [deepcopy(item.regions) for item in project.language_items]
    options = arrangement_request_detail(db, request.id)['scope_options']
    assert len(options) == 3
    assert [o['city'] for o in options] == ['广州', '深圳', '北京']
    assert options[0]['language_ids'] == options[1]['language_ids'] != options[2]['language_ids']
    project.language_items[0].regions = list(reversed(project.language_items[0].regions)); db.flush()
    assert {o['key'] for o in request_scope_options(db, request)} == {o['key'] for o in options}
    assert before[1] == project.language_items[1].regions
    request.source_type = 'other'; request.annotation_project_id = None
    assert request_scope_options(db, request)[0]['city'] == ''
    assert '未配置城市' in request_scope_options(db, request)[0]['label']


def test_scope_shared_accounts_readback_replacement_and_other_request_preserved(db, context):
    from resource_arrangement_service import assign_request, arrangement_request_detail, get_cells, read_arrangement
    from resource_development_schemas import RequestArrangementWrite
    request, project = scoped_request(db, context)
    other, _ = request_context(db, context)
    options = arrangement_request_detail(db, request.id)['scope_options']
    accounts = [p.id for p in context[3]]
    day = assign(db, context, other, [accounts[0]])
    cells = get_cells(db, day)
    cells[0].remarks = '保留账号备注'; db.flush()
    day = assign_request(db, context[0], request.id, day.work_date, RequestArrangementWrite(
        revision=day.revision, platform_ids=accounts, selected_scope_keys=[options[1]['key']], arrangement_note='  优先深圳  '))
    for cell in get_cells(db, day):
        target = next(t for t in cell.targets if t['request_id'] == str(request.id))
        assert target['scope'] == [options[1]] and target['arrangement_note'] == '优先深圳'
    assert next(c for c in get_cells(db, day) if c.platform_id == accounts[0]).remarks == '保留账号备注'
    assert project.language_items[0].regions[0]['city'] == '广州' and request.request_detail == '需求'
    # 旧客户端省略新增字段必须保留内容。
    day = assign(db, context, request, accounts, day.revision)
    assert all(next(t for t in c['targets'] if t['request_id'] == str(request.id))['arrangement_note'] == '优先深圳'
               for c in read_arrangement(db, context[0], day.work_date)['cells'])
    day = assign(db, context, request, [], day.revision)
    assert arrangement_request_detail(db, request.id)['arrangements'] == []
    assert any(t['request_id'] == str(other.id) for c in get_cells(db, day) for t in c.targets)


def test_scope_full_day_carry_completion_and_date_isolation(db, context):
    from resource_arrangement_service import assign_request, arrangement_request_detail, carry_preview, get_cells, target_write, save_arrangement
    from resource_development_schemas import RequestArrangementWrite
    request, _ = scoped_request(db, context)
    options = arrangement_request_detail(db, request.id)['scope_options']
    day = assign_request(db, context[0], request.id, date(2026, 10, 12), RequestArrangementWrite(
        revision=0, platform_ids=[context[3][0].id], selected_scope_keys=[options[0]['key']], arrangement_note='明日安排'))
    cell = get_cells(db, day)[0]
    # 整日旧载荷不提供新增字段；仍不得清除已存选择。
    save(db, context, day=day.work_date, revision=day.revision, cells=[dict(platform_id=cell.platform_id,
        targets=[dict(kind='request_project', request_id=request.id)], remarks='账号说明')])
    assert cell.targets[0]['arrangement_note'] == '明日安排'
    preview = carry_preview(db, context[0], date(2026, 10, 13))
    copied = preview['cells'][0]
    next_day = save_arrangement(db, context[0], date(2026, 10, 13), ArrangementWrite(revision=0, carried_from=day.work_date,
        cells=[dict(platform_id=copied['platform_id'], targets=[target_write(t) for t in copied['targets']])]))
    assert get_cells(db, next_day)[0].targets[0]['scope'] == [options[0]]
    assign_request(db, context[0], request.id, next_day.work_date, RequestArrangementWrite(revision=next_day.revision,
        platform_ids=[cell.platform_id], selected_scope_keys=[options[2]['key']], arrangement_note='后天安排'))
    assert cell.targets[0]['arrangement_note'] == '明日安排'


def test_scope_rejects_foreign_empty_or_changed_choices(db, context):
    from resource_arrangement_service import assign_request, arrangement_request_detail
    from resource_development_schemas import RequestArrangementWrite
    request, project = scoped_request(db, context)
    options = arrangement_request_detail(db, request.id)['scope_options']
    for keys in [[], ['forged-key'], [options[0]['key']] * 2]:
        with pytest.raises(HTTPException) as error:
            assign_request(db, context[0], request.id, date(2026, 10, 12), RequestArrangementWrite(
                revision=0, platform_ids=[context[3][0].id], selected_scope_keys=keys))
        assert error.value.status_code == 409
    project.language_items[0].regions = [{'city': '佛山'}]; db.flush()
    with pytest.raises(HTTPException):
        assign_request(db, context[0], request.id, date(2026, 10, 12), RequestArrangementWrite(
            revision=0, platform_ids=[context[3][0].id], selected_scope_keys=[options[0]['key']]))


def test_all_status_page_with_batch_platform_summary(db, context, monkeypatch):
    from routers.resource_requests import read_request_page
    confirmed, _ = request_context(db, context)
    draft, _ = request_context(db, context, status='draft')
    paused, _ = request_context(db, context, status='paused')
    cancelled, _ = request_context(db, context, status='cancelled')
    assign(db, context, confirmed, [context[3][0].id])
    # 路由直接调用需显式给出 Query 参数，避免使用 FastAPI 的参数描述对象。
    page = read_request_page(skip=0, limit=5, field_filters=None, include_arrangements=True, db=db)
    assert page['total'] == 4
    assert {row['id'] for row in page['items']} == {r.id for r in [confirmed, draft, paused, cancelled]}
    assert next(row for row in page['items'] if row['id'] == confirmed.id)['arrangements'][0]['platform_name']


def test_scope_legacy_read_does_not_write_and_invalid_carry_is_skipped(db, context):
    from resource_arrangement_service import assign_request, arrangement_request_detail, get_cells, read_arrangement, carry_preview
    from resource_development_schemas import RequestArrangementWrite
    request, project = scoped_request(db, context)
    day = assign(db, context, request, [context[3][0].id])
    cell = get_cells(db, day)[0]
    legacy = deepcopy(cell.targets)
    legacy[0].pop('scope'); legacy[0].pop('arrangement_note')
    cell.targets = legacy; db.flush()
    before, revision = deepcopy(cell.targets), day.revision
    assert len(read_arrangement(db, context[0], day.work_date)['cells'][0]['targets'][0]['scope']) == 3
    assert read_arrangement(db, context[0], day.work_date)['cells'][0]['targets'][0]['scope_recorded'] is False
    assert cell.targets == before and day.revision == revision
    option = arrangement_request_detail(db, request.id)['scope_options'][0]
    day = assign_request(db, context[0], request.id, day.work_date, RequestArrangementWrite(
        revision=day.revision, platform_ids=[cell.platform_id], selected_scope_keys=[option['key']], arrangement_note='保留历史'))
    project.language_items[0].regions = [{'city': '佛山'}]; db.flush()
    displayed = read_arrangement(db, context[0], day.work_date)['cells'][0]['targets'][0]
    assert displayed['scope'] == [option] and not displayed['active']
    preview = carry_preview(db, context[0], date(2026, 10, 13))
    assert preview['cells'][0]['targets'] == [] and any('语言或城市' in text for text in preview['warnings'])


def test_scope_change_resets_completion_and_repeat_preserves_completion(db, context):
    from resource_arrangement_service import assign_request, arrangement_request_detail, complete_arrangement, get_cells
    from resource_development_schemas import RequestArrangementWrite
    request, _ = scoped_request(db, context)
    options = arrangement_request_detail(db, request.id)['scope_options']
    day = save(db, context, day=date(2026, 10, 12))
    cell = get_cells(db, day)[0]
    def write(note):
        return assign_request(db, context[0], request.id, day.work_date, RequestArrangementWrite(revision=day.revision,
            platform_ids=[cell.platform_id], selected_scope_keys=[options[0]['key']], arrangement_note=note))
    write('初次安排')
    complete_arrangement(db, context[1], day.work_date, cell.platform_id, ArrangementCompletionWrite(revision=day.revision, completed=True))
    write('初次安排'); assert cell.completed
    write('新增要求'); assert not cell.completed
