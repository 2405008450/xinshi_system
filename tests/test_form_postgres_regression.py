"""真实接口和 PostgreSQL 回归；没有显式隔离库配置时跳过，绝不使用默认库。"""
import os
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.fixture
def form_api():
    url = os.getenv('XINSHI_FORM_TEST_DATABASE_URL')
    if not url:
        pytest.skip('未配置独立表单回归数据库')
    parsed = make_url(url)
    assert parsed.host in {'127.0.0.1', 'localhost'}
    assert parsed.port and 15000 <= parsed.port <= 15999
    assert parsed.database.startswith('xinshi_form_regression_')
    assert os.environ.get('DATABASE_URL') == url
    engine = create_engine(url, connect_args={'options': '-c statement_timeout=15000 -c lock_timeout=5000'})
    with engine.connect() as check:
        assert check.scalar(text('SELECT purpose FROM public.form_regression_marker')) == 'isolated_form_regression'
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.annotation_ops import router as annotation_router
    from routers.clients import router as clients_router
    from routers.roles import router as roles_router
    from routers.consultations import router as consultations_router
    from routers.translation_projects import router as translation_router
    from routers.interpretation_projects import router as interpretation_router
    from routers.annotation_projects import router as projects_router
    from routers.recruitment_projects import router as recruitment_router
    from routers.resource_requests import router as requests_router
    from routers.talents import router as talents_router
    from models import AppUser, Role, UserRole, RolePermission
    from annotation_models import AnnotationProject
    from resource_models import ResourcePerson, ResourceCapability
    import recruitment_models  # 注册工作台关系指向的模型，与正式入口保持一致。

    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, autoflush=False, join_transaction_mode='create_savepoint')
    app = FastAPI()
    for router in [annotation_router, clients_router, roles_router, consultations_router, translation_router,
                   interpretation_router, projects_router, recruitment_router, requests_router, talents_router]:
        app.include_router(router)
    users = {}
    for name, codes in [('admin', []), ('writer', ['projects:read', 'projects:write']), ('reader', ['projects:read'])]:
        user = AppUser(id=uuid4(), username=f'qa_{name}_{uuid4().hex[:8]}', password_hash='unused-test-hash')
        role = Role(id=uuid4(), role_name='admin' if name == 'admin' else f'qa_{name}_{uuid4().hex[:8]}')
        db.add_all([user, role])
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.add_all([RolePermission(role_id=role.id, permission_code=code) for code in codes])
        users[name] = user
    project = AnnotationProject(id=uuid4(), order_no=f'QA-{uuid4().hex[:12]}', project_name='表单回归项目')
    people = [ResourcePerson(id=uuid4(), full_name=f'回归标注员{index}') for index in range(3)]
    db.add_all([project, *people])
    db.flush()
    db.add_all([ResourceCapability(person_id=person.id, capability_type='annotation', status='active') for person in people])
    db.commit()
    state = SimpleNamespace(user=users['admin'])
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: state.user
    client = TestClient(app)
    try:
        yield SimpleNamespace(client=client, db=db, project=project, people=people, users=users, state=state)
    finally:
        client.close()
        db.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def trial_payload(ctx, person=0, **changes):
    return {'project_id': str(ctx.project.id), 'person_id': str(ctx.people[person].id), **changes}


def test_trial_create_change_round_clear_and_read(form_api):
    c = form_api.client
    one = c.post('/annotation-ops/trials', json=trial_payload(form_api, quote_amount=12, billing_unit='item'))
    assert one.status_code == 201, one.text
    two = c.post('/annotation-ops/trials', json=trial_payload(form_api, person=1, round_no=2))
    assert two.status_code == 201, two.text
    saved = one.json()
    response = c.put('/annotation-ops/trials/' + saved['id'], json=trial_payload(
        form_api, round_no=2, sequence_no=saved['sequence_no'], quote_amount=None, billing_unit=None))
    assert response.status_code == 200, response.text
    assert response.json()['sequence_no'] == 2
    rows = c.get('/annotation-ops/trials', params={'project_id': str(form_api.project.id)}).json()
    row = next(row for row in rows if row['id'] == saved['id'])
    assert row['round_no'] == 2 and row['quote_amount'] is None and row['billing_unit'] is None


@pytest.mark.parametrize('field', ['project_id', 'person_id'])
def test_trial_required_field_422_without_partial_write(form_api, field):
    payload = trial_payload(form_api)
    del payload[field]
    response = form_api.client.post('/annotation-ops/trials', json=payload)
    assert response.status_code == 422
    assert any(item['loc'] == ['body', field] for item in response.json()['detail'])
    assert form_api.db.scalar(text('SELECT count(*) FROM annotation_trial_record')) == 0


def test_trial_duplicate_and_constraint_rollback(form_api):
    c = form_api.client
    first = c.post('/annotation-ops/trials', json=trial_payload(form_api))
    assert first.status_code == 201, first.text
    assert c.post('/annotation-ops/trials', json=trial_payload(form_api)).status_code == 400
    conflict = c.post('/annotation-ops/trials', json=trial_payload(form_api, person=1, sequence_no=1))
    assert conflict.status_code == 400
    assert isinstance(conflict.json()['detail'], dict)
    assert 'SQL' not in conflict.text
    assert form_api.db.scalar(text('SELECT count(*) FROM annotation_trial_record')) == 1
    retry = c.post('/annotation-ops/trials', json=trial_payload(form_api, person=1))
    assert retry.status_code == 201 and retry.json()['sequence_no'] == 2


@pytest.mark.parametrize('role, expected', [('admin', 201), ('writer', 201), ('reader', 403)])
def test_trial_real_permission_rows(form_api, role, expected):
    form_api.state.user = form_api.users[role]
    response = form_api.client.post('/annotation-ops/trials', json=trial_payload(form_api))
    assert response.status_code == expected, response.text


def test_role_duplicate_edit_rolls_back_and_readback(form_api):
    c = form_api.client
    one = c.post('/roles/', json={'role_name': '回归角色一'}).json()
    two = c.post('/roles/', json={'role_name': '回归角色二'}).json()
    conflict = c.put('/roles/' + two['id'], json={'role_name': one['role_name']})
    assert conflict.status_code == 400
    assert conflict.json()['detail']['fieldErrors'][0]['path'] == 'role_name'
    assert c.get('/roles/' + two['id']).json()['role_name'] == '回归角色二'
    assert c.put('/roles/' + two['id'], json={'description': '已修改'}).status_code == 200
    assert c.get('/roles/' + two['id']).json()['description'] == '已修改'


def test_client_create_edit_clear_idempotency_and_readback(form_api):
    c = form_api.client
    payload = {'client_name': '回归客户', 'client_short_name': '回归', 'remarks': '待清空'}
    headers = {'X-Idempotency-Key': uuid4().hex}
    one = c.post('/clients/', json=payload, headers=headers)
    assert one.status_code == 201, one.text
    repeated = c.post('/clients/', json=payload, headers=headers)
    assert repeated.json()['id'] == one.json()['id']
    record_id = one.json()['id']
    response = c.put('/clients/' + record_id, json={'remarks': None, 'client_short_name': '已改'})
    assert response.status_code == 200, response.text
    row = c.get('/clients/' + record_id).json()
    assert row['remarks'] is None and row['client_short_name'] == '已改'


@pytest.mark.parametrize('path', ['/projects/translation/', '/projects/interpretation/',
                                  '/projects/annotation/', '/projects/recruitment/'])
def test_project_create_edit_readback(form_api, path):
    payload = {'project_name': '回归项目初始名称', 'client_short_name': '回归自动客户'}
    response = form_api.client.post(path, json=payload)
    assert response.status_code == 201, response.text
    record_id = response.json()['id']
    payload['project_name'] = '回归项目修改名称'
    response = form_api.client.put(path + record_id, json=payload)
    assert response.status_code == 200, response.text
    saved = form_api.client.get(path + record_id)
    assert saved.status_code == 200, saved.text
    assert saved.json()['project_name'] == payload['project_name']


def test_consultation_create_edit_readback(form_api):
    response = form_api.client.post('/consultations/', json={'project_name': '回归咨询', 'consultation_type': 'translation',
        'client_source': '线上咨询', 'consultation_method': 'email', 'consultation_description': '回归咨询描述'})
    assert response.status_code == 201, response.text
    record_id = response.json()['id']
    response = form_api.client.put('/consultations/' + record_id, json={'remarks': '回归修改'})
    assert response.status_code == 200, response.text
    assert form_api.client.get('/consultations/' + record_id).json()['remarks'] == '回归修改'


def test_talent_create_edit_readback(form_api):
    payload = {'full_name': '回归人才新增', 'status': 'standby', 'capabilities': [{'capability_type': 'annotation', 'status': 'active'}]}
    response = form_api.client.post('/talents/', json=payload)
    assert response.status_code == 201, response.text
    record_id = response.json()['id']
    payload['full_name'] = '回归人才已改'
    response = form_api.client.put('/talents/' + record_id, json=payload)
    assert response.status_code == 200, response.text
    assert form_api.client.get('/talents/' + record_id).json()['full_name'] == payload['full_name']


def test_resource_request_draft_create_edit_readback(form_api):
    payload = {'source_type': 'other', 'request_category': 'other', 'other_source_name': '回归来源',
               'request_status': 'draft', 'request_detail': '回归草稿'}
    response = form_api.client.post('/resource-requests/', json=payload)
    assert response.status_code == 201, response.text
    record_id = response.json()['id']
    payload['request_detail'] = '草稿修改'
    response = form_api.client.put('/resource-requests/' + record_id, json=payload)
    assert response.status_code == 200, response.text
    assert form_api.client.get('/resource-requests/' + record_id).json()['request_detail'] == payload['request_detail']
