"""使用专用隔离库验证共享会话分类、原权限和迁移幂等性。"""
from pathlib import Path
from uuid import UUID, uuid4
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from database import get_db
from routers.auth import get_current_user
from routers import chat_session_categories as api
from routers.chat_sessions import sessions
from chat_session_category_models import ChatSessionCategory, ChatSessionCategoryLink
import chat_session_category_service as service
from test_resource_issues import environment


def client_for(db, user):
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def category(db, data, name='高校团队'):
    return api.create(api.CategoryCreate(name=name), db, data['users']['admin'])


def test_catalog_management_versions_reserved_and_duplicate_names(environment):
    db, data = environment
    ordinary = client_for(db, data['users']['collector'])
    admin = client_for(db, data['users']['admin'])
    assert ordinary.get('/chat/session-categories').json()['can_manage'] is False
    assert ordinary.post('/chat/session-categories', json={'name': '无权新增'}).status_code == 403
    for name in ('', '  ', '字' * 81):
        assert admin.post('/chat/session-categories', json={'name': name}).status_code == 422
    assert admin.post('/chat/session-categories', json={'name': '未读'}).status_code == 409
    row = admin.post('/chat/session-categories', json={'name': '  Team A  '}).json()
    assert row['name'] == 'Team A' and row['updated_at'].endswith('+08:00')
    assert admin.post('/chat/session-categories', json={'name': 'team a'}).status_code == 409
    response = admin.put('/chat/session-categories/' + row['id'], json={'name': '高校组', 'revision': row['revision']})
    assert response.status_code == 200 and response.json()['id'] == row['id']
    assert admin.put('/chat/session-categories/' + row['id'], json={'active': False, 'revision': row['revision']}).status_code == 409
    assert client_for(db, data['users']['inactive']).get('/chat/session-categories').status_code == 403


@pytest.mark.parametrize('kind', ['translation', 'annotation', 'direct'])
def test_shared_multiple_categories_incremental_updates_and_stable_ids(environment, kind):
    db, data = environment
    first, second = category(db, data), category(db, data, '重点跟进')
    actor = data['users']['collector']
    target = data[kind].id
    for row in (first, second, first):
        service.set_membership(db, actor, kind, target, UUID(row['id']), True)
    assert db.query(ChatSessionCategoryLink).count() == 2
    ids = service.memberships(db, data['users']['proposer'], kind, target)
    assert set(ids) == {first['id'], second['id']}
    api.update(UUID(first['id']), api.CategoryUpdate(name='改名后', revision=first['revision']), db, data['users']['admin'])
    assert set(service.memberships(db, actor, kind, target)) == set(ids)
    service.set_membership(db, actor, kind, target, UUID(first['id']), False)
    service.set_membership(db, actor, kind, target, UUID(first['id']), False)
    assert service.memberships(db, actor, kind, target) == [second['id']]


@pytest.mark.parametrize('kind', ['translation', 'annotation', 'direct'])
def test_unauthorized_membership_and_catalog_do_not_expand_access(environment, kind):
    db, data = environment
    row = category(db, data)
    cid, target = UUID(row['id']), data[kind].id
    service.set_membership(db, data['users']['collector'], kind, target, cid, True)
    outsider = client_for(db, data['users']['outsider'])
    base = f'/chat/sessions/{kind}/{target}/categories'
    assert outsider.get('/chat/session-categories').status_code == 200
    for method, path in [('get', base), ('put', f'{base}/{cid}'), ('delete', f'{base}/{cid}')]:
        assert getattr(outsider, method)(path).status_code in (403, 404)
    assert sessions(db, data['users']['outsider'])['items'] == []
    if kind == 'direct':
        with pytest.raises(HTTPException):
            service.memberships(db, data['users']['admin'], kind, target)


def test_inactive_categories_preserve_links_and_do_not_change_directory(environment):
    db, data = environment
    row = category(db, data)
    cid = UUID(row['id'])
    before = {item['key'] for item in sessions(db, data['users']['collector'])['items']}
    service.set_membership(db, data['users']['collector'], 'annotation', data['annotation'].id, cid, True)
    after = sessions(db, data['users']['collector'])
    assert {item['key'] for item in after['items']} == before  # 不会自动关注标注项目。
    api.update(cid, api.CategoryUpdate(active=False, revision=1), db, data['users']['admin'])
    assert service.memberships(db, data['users']['collector'], 'annotation', data['annotation'].id) == []
    assert db.query(ChatSessionCategoryLink).count() == 1
    with pytest.raises(HTTPException) as stopped:
        service.set_membership(db, data['users']['collector'], 'annotation', data['annotation'].id, cid, True)
    assert stopped.value.status_code == 409
    api.update(cid, api.CategoryUpdate(active=True, revision=2), db, data['users']['admin'])
    assert service.memberships(db, data['users']['collector'], 'annotation', data['annotation'].id) == [row['id']]


def test_sessions_only_decorate_authorized_rows_and_keep_topic_links(environment):
    db, data = environment
    row = category(db, data)
    for kind in ('translation', 'direct'):
        service.set_membership(db, data['users']['collector'], kind, data[kind].id, UUID(row['id']), True)
    ordinary = sessions(db, data['users']['collector'])
    matching = [item for item in ordinary['items'] if row['id'] in item['category_ids']]
    assert len(matching) == 2
    assert len([item for item in sessions(db, data['users']['manager'])['items'] if row['id'] in item['category_ids']]) == 1
    from chat_topic_models import ChatMessageTopic
    assert db.query(ChatMessageTopic).count() == 0


def test_unmigrated_schema_degrades_without_querying_missing_tables(environment, monkeypatch):
    db, data = environment
    monkeypatch.setattr(service, 'schema_ready', lambda _db: False)
    result = sessions(db, data['users']['collector'])
    assert result['session_categories'] == {'ready': False, 'hierarchy_ready': False, 'can_manage': False, 'items': []}
    assert all(item['category_ids'] == [] for item in result['items'])
    assert client_for(db, data['users']['admin']).post('/chat/session-categories', json={'name': '待迁移'}).status_code == 503


def test_repeated_migration_preserves_shared_categories_and_links(environment):
    db, data = environment
    row = category(db, data)
    service.set_membership(db, data['users']['collector'], 'direct', data['direct'].id, UUID(row['id']), True)
    sql = (Path(__file__).resolve().parents[1] / 'data/migrations/20261019_chat_session_categories.sql').read_text(encoding='utf-8')
    # 在测试事务内执行DDL主体，不能让脚本的COMMIT越过隔离回滚边界。
    body = sql[sql.index('BEGIN;') + len('BEGIN;'):sql.rindex('COMMIT;')]
    db.connection().exec_driver_sql(body)
    db.connection().exec_driver_sql(body)
    assert db.get(ChatSessionCategory, UUID(row['id'])).name == '高校团队'
    assert db.query(ChatSessionCategoryLink).count() == 1
