"""双线进度的真实 PostgreSQL 回归，只允许独立本机测试实例。"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, make_url, text
from sqlalchemy.orm import Session

from annotation_customer_progress_models import AnnotationCustomerProgress
from annotation_customer_progress_schemas import CustomerProgressDelete, CustomerProgressUpdate, CustomerProgressWrite
from annotation_customer_progress_service import (
    attach_customer_progress_summary, create_customer_progress, delete_customer_progress,
    list_customer_progress, search_progress_records, update_customer_progress,
)
from annotation_progress_time import business_datetime
from concurrency import StaleUpdateError


@pytest.fixture
def environment():
    url = os.getenv('CUSTOMER_PROGRESS_TEST_DATABASE_URL')
    if not url:
        pytest.skip('通过 tools/run_annotation_customer_progress_tests.py 创建独立隔离实例')
    parsed = make_url(url)
    assert parsed.host == '127.0.0.1' and parsed.username == 'customer_progress_test' and parsed.database == 'postgres'
    import main
    from models import AppUser, Base, Role, RolePermission, UserRole
    from annotation_models import AnnotationProject
    bootstrap = create_engine(url)
    schema = 'progress_' + uuid4().hex
    with bootstrap.begin() as connection:
        connection.execute(text('CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public'))
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={'options': f'-c search_path={schema},public -c timezone=UTC'})
    with engine.begin() as connection:
        connection.execute(text('CREATE SEQUENCE chat_message_sequence'))
    Base.metadata.create_all(engine, tables=[table for table in Base.metadata.sorted_tables if table.name != 'annotation_customer_progress'], checkfirst=False)
    migration = (Path(__file__).resolve().parents[1] / 'data/migrations/20261010_annotation_customer_progress.sql').read_text(encoding='utf-8')
    with engine.connect() as connection:
        connection.execute(text(migration))
        connection.execute(text(migration))
    db = Session(engine, expire_on_commit=False)
    role = Role(role_name='customer-progress-' + uuid4().hex[:8])
    users = [AppUser(username='progress-' + uuid4().hex, full_name=f'客户进度测试{i}', password_hash='disabled', is_active=True) for i in range(3)]
    parent = AnnotationProject(order_no='AP-QA-' + uuid4().hex[:10].upper(), project_name='双线进度隔离验收', project_types=['text_annotation'], project_status='trial_preparation')
    db.add_all([role, *users, parent]); db.flush()
    child = AnnotationProject(order_no=parent.order_no+'.001', project_name='子订单隔离验收', parent_project_id=parent.id, child_sequence_no=1, project_types=['text_annotation'], project_status='trial_preparation')
    db.add(child)
    db.add_all([RolePermission(role_id=role.id, permission_code=code) for code in ['projects:read', 'projects:write', 'system:audit:read']])
    db.add_all(UserRole(role_id=role.id, user_id=user.id) for user in users[:2]); db.commit()
    try:
        yield db, users, parent, child, engine
    finally:
        main.app.dependency_overrides.clear(); db.close(); engine.dispose()
        with bootstrap.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        bootstrap.dispose()


def add(db, project, user, note='等待客户确认', when='2026-10-10T17:30:00+08:00'):
    return create_customer_progress(db, project.id, CustomerProgressWrite(change_note=note, effective_on=when), user.id)


def test_customer_progress_contract_and_timezone():
    assert CustomerProgressWrite(change_note='  客户确认  ', effective_on='2026-10-10T09:30:00Z').effective_on.isoformat() == '2026-10-10T17:30:00+08:00'
    for note in ['', '  ', '甲' * 10001]:
        with pytest.raises(ValueError):
            CustomerProgressWrite(change_note=note)
    with pytest.raises(ValueError):
        CustomerProgressDelete(reason='删除', expected_updated_at=None)


def test_independent_parent_child_and_stable_summary(environment):
    db, users, parent, child, engine = environment
    latest = add(db, parent, users[0], '最新客户反馈')
    older = add(db, parent, users[0], '补录客户反馈', '2026-10-09T17:30:00+08:00')
    assert [row['id'] for row in list_customer_progress(db, parent.id)] == [latest['id'], older['id']]
    assert list_customer_progress(db, child.id) == []
    assert parent.project_status == 'trial_preparation'
    from annotation_ops_models import AnnotationProjectStatusHistory
    assert db.query(AnnotationProjectStatusHistory).count() == 0
    statements = []
    def observe(_connection, _cursor, statement, *_args):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', observe)
    try:
        attach_customer_progress_summary(db, [parent, child])
    finally:
        event.remove(engine, 'before_cursor_execute', observe)
    assert parent.latest_customer_progress_note == '最新客户反馈'
    assert child.latest_customer_progress_note is None
    assert sum('row_number' in sql.lower() for sql in statements) == 1
    assert business_datetime(parent.latest_customer_progress_effective_on).isoformat().endswith('+08:00')


def test_edit_versions_and_delete_audit_preserve_original(environment):
    db, users, parent, _child, _engine = environment
    row = add(db, parent, users[0])
    updated = update_customer_progress(db, row['id'], CustomerProgressUpdate(change_note='客户已确认', effective_on='2026-10-10 18:00:00', expected_updated_at=row['updated_at']), users[1].id)
    assert updated['changed_by'] == users[0].id and updated['changed_at'] == row['changed_at']
    assert updated['updated_by'] == users[1].id and updated['updated_at'] > row['updated_at']
    with pytest.raises(StaleUpdateError):
        delete_customer_progress(db, row['id'], CustomerProgressDelete(reason='旧版本', expected_updated_at=row['updated_at']), users[0].id)
    db.rollback()
    assert delete_customer_progress(db, row['id'], CustomerProgressDelete(reason='内容录错', expected_updated_at=updated['updated_at'].astimezone(timezone.utc)), users[1].id)
    from project_audit_models import ProjectOperationAudit
    audit = db.query(ProjectOperationAudit).one()
    assert audit.operation_type == 'progress_delete' and audit.change_reason == '内容录错'
    assert audit.project_snapshot['deleted_progress_record']['track'] == 'customer'
    assert audit.project_snapshot['deleted_progress_record']['change_note'] == '客户已确认'
    assert audit.project_snapshot['deleted_progress_record']['effective_on'].endswith('+08:00')
    from annotation_progress_time import business_now
    assert abs((audit.occurred_at - business_now()).total_seconds()) < 5
    client = api_client(db, users[0])
    response = client.get('/project-operation-audits/', params={'operation_type':'progress_delete'})
    assert response.status_code == 200, response.text
    assert response.json()['total'] == 1
    assert response.json()['items'][0]['occurred_at'].endswith('+08:00')
    attach_customer_progress_summary(db, [parent])
    assert parent.latest_customer_progress_note is None


def test_concurrent_same_version_only_one_writer_succeeds(environment):
    db, users, parent, _child, engine = environment
    row = add(db, parent, users[0])
    def edit(note):
        with Session(engine) as session:
            try:
                update_customer_progress(session, row['id'], CustomerProgressUpdate(change_note=note, effective_on=row['effective_on'], expected_updated_at=row['updated_at']), users[0].id)
                return 'saved'
            except StaleUpdateError:
                session.rollback(); return 'stale'
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(edit, ['反馈一', '反馈二']))
    assert sorted(results) == ['saved', 'stale']


def test_unified_search_pagination_wildcards_and_date_boundary(environment):
    db, users, parent, _child, _engine = environment
    from annotation_ops_models import AnnotationProjectStatusHistory
    from datetime import datetime
    db.add(AnnotationProjectStatusHistory(project_id=parent.id, from_status='trial_preparation', to_status='trial_preparation', entry_kind='progress', change_note='项目完成 50%_等待确认', effective_on=datetime(2026, 10, 10, 8), changed_at=datetime(2026, 10, 10, 8), updated_at=datetime(2026, 10, 10, 8)))
    db.commit()
    add(db, parent, users[0], '客户完成 50%_等待确认', '2026-10-10T15:59:59.999999Z')
    add(db, parent, users[0], '客户完成 50%_次日记录', '2026-10-10T16:00:00Z')
    add(db, parent, users[0], '50X待确认', '2026-10-10T17:00:00+08:00')
    filters = dict(track='all', keyword='50%_', date_from=date(2026, 10, 10), date_to=date(2026, 10, 10), limit=1)
    first = search_progress_records(db, **filters)
    second = search_progress_records(db, **filters, skip=1)
    empty = search_progress_records(db, **filters, skip=5)
    assert first['total'] == second['total'] == empty['total'] == 2
    assert first['items'][0]['track'] == 'customer' and first['items'][0]['to_status'] is None
    assert second['items'][0]['track'] == 'project'
    assert empty['items'] == []
    assert search_progress_records(db, track='customer', keyword='50%_', date_from=date(2026, 10, 10), date_to=date(2026, 10, 10))['total'] == 1


def api_client(db, user):
    import main
    from database import get_db
    from routers.auth import get_current_user
    main.app.dependency_overrides[get_db] = lambda: db
    main.app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(main.app)


def test_api_defaults_errors_permissions_and_versions(environment):
    db, users, parent, _child, _engine = environment
    client = api_client(db, users[0])
    path = f'/annotation-ops/projects/{parent.id}/customer-progress'
    created = client.post(path, json={'change_note':'客户确认','effective_on':'2026-10-10T09:30:00Z'})
    assert created.status_code == 201, created.text
    row = created.json()
    assert row['effective_on'] == '2026-10-10T17:30:00+08:00'
    assert client.get('/annotation-ops/status-history/recent').json()['total'] == 0
    assert client.get('/annotation-ops/status-history/recent', params={'track':'all'}).json()['total'] == 1
    assert client.get('/annotation-ops/status-history/recent', params={'track':'invalid'}).status_code == 422
    assert client.patch(f"/annotation-ops/customer-progress/{row['id']}", json={'change_note':'修改','effective_on':row['effective_on']}).status_code == 422
    payload = {'change_note':'客户修改','effective_on':row['effective_on'],'expected_updated_at':row['updated_at']}
    assert client.patch(f"/annotation-ops/customer-progress/{row['id']}", json=payload).status_code == 200
    assert client.patch(f"/annotation-ops/customer-progress/{row['id']}", json=payload).status_code == 409
    client = api_client(db, users[2])
    assert client.get(path).status_code == 403
    assert client.post(path, json={'change_note':'越权'}).status_code == 403
    from models import Role, RolePermission, UserRole
    read_role = Role(role_name='progress-reader-' + uuid4().hex)
    db.add(read_role); db.flush()
    db.add(RolePermission(role_id=read_role.id, permission_code='projects:read'))
    db.add(UserRole(role_id=read_role.id, user_id=users[2].id)); db.commit()
    assert client.get(path).status_code == 200
    assert client.post(path, json={'change_note':'只读账号不能写入'}).status_code == 403


def test_missing_migration_keeps_existing_summary_and_reports_unavailable(environment):
    db, users, parent, _child, engine = environment
    with engine.begin() as connection:
        connection.execute(text('DROP TABLE annotation_customer_progress'))
    attach_customer_progress_summary(db, [parent])
    assert parent.latest_customer_progress_note is None
    client = api_client(db, users[0])
    response = client.get(f'/annotation-ops/projects/{parent.id}/customer-progress')
    assert response.status_code == 503 and '数据库迁移' in response.json()['detail']
    assert client.get('/annotation-ops/status-history/recent', params={'track':'all'}).status_code == 200
