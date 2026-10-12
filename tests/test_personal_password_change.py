"""个人改密接口使用内存隔离数据库，禁止访问日常业务库。"""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import JSON, MetaData, create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main as _registered_models
import auth_security
from auth_security_models import LoginCaptchaChallenge, LoginSecurityEvent, LoginThrottleState, RevokedAccessToken
from crud import reset_user_password
from database import get_db
from models import AppUser
from routers import auth
from routers import notifications
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def password_app(monkeypatch):
    monkeypatch.setattr(auth, 'SECRET_KEY', 'isolated-password-change-secret')
    monkeypatch.setenv('AUTH_THROTTLE_HMAC_KEY', 'isolated-password-change-hmac')
    monkeypatch.setattr(auth, 'get_user_roles_with_role_names', lambda *_: [])
    monkeypatch.setattr(auth, 'get_user_permission_codes', lambda *_: [])
    engine = create_engine('sqlite+pysqlite:///:memory:',
                           connect_args={'check_same_thread': False}, poolclass=StaticPool)
    # 只调整隔离表的 JSON 存储类型，不改变业务模型或数据库。
    isolated_users = AppUser.__table__.to_metadata(MetaData())
    isolated_users.c.fixed_tasks.type = JSON()
    isolated_users.c.fixed_tasks.server_default = None
    isolated_users.c.id.server_default = None
    isolated_users.indexes.clear()  # 邮箱表达式索引属于 PostgreSQL，改密测试不涉及邮箱。
    isolated_users.create(engine)
    for model in (LoginCaptchaChallenge, LoginThrottleState, LoginSecurityEvent, RevokedAccessToken):
        model.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        user = AppUser(id=uuid4(), username='password-user', full_name='改密验收',
                       password_hash=auth.hash_password('OldPwd23'), is_active=True)
        other = AppUser(id=uuid4(), username='other-user', password_hash=auth.hash_password('Other234'), is_active=True)
        db.add_all([user, other]); db.commit()
        tokens = [auth.create_user_access_token(user), auth.create_user_access_token(user)]
        user_id, other_id, before = user.id, other.id, other.password_hash
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(notifications.router)
    monkeypatch.setattr(notifications, 'SessionLocal', sessions)
    monkeypatch.setattr(notifications, 'count_unread_notifications', lambda *args, **kwargs: 0)

    def override_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, sessions, tokens, user_id, other_id, before
    engine.dispose()


def change(client, token, **overrides):
    return client.put('/auth/password', headers={'Authorization': 'Bearer ' + token},
                      json={'current_password': 'OldPwd23', 'new_password': 'NewPwd45',
                            'confirm_password': 'NewPwd45', **overrides})


def test_regular_user_changes_password_and_all_old_tokens_expire(password_app):
    client, sessions, tokens, user_id, other_id, other_hash = password_app
    # 客户端传来的其他账号 ID 不会决定被修改的账号。
    response = change(client, tokens[0], user_id=str(other_id))
    assert response.status_code == 204
    assert response.headers['cache-control'] == 'no-store'
    with sessions() as db:
        user = db.get(AppUser, user_id)
        assert auth.verify_password('NewPwd45', user.password_hash)
        assert not auth.verify_password('OldPwd23', user.password_hash)
        assert db.get(AppUser, other_id).password_hash == other_hash
        assert db.scalar(select(LoginSecurityEvent.event_type)) == 'password_changed'
        fresh = auth.create_user_access_token(user)
        payload = auth.jwt.decode(fresh, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        assert len(payload['pwdv']) == 64 and user.password_hash not in str(payload)
    for token in tokens:
        assert client.get('/auth/session', headers={'Authorization': 'Bearer ' + token}).status_code == 401
    assert client.get('/auth/session', headers={'Authorization': 'Bearer ' + fresh}).status_code == 200
    accepted = client.post('/auth/login/json', json={'username': 'password-user', 'password': 'NewPwd45'})
    assert accepted.status_code == 200
    denied = client.post('/auth/login/json', json={'username': 'password-user', 'password': 'OldPwd23'})
    assert denied.status_code == 401


@pytest.mark.parametrize('overrides,field,status', [
    ({'current_password': 'Wrong234'}, 'current_password', 400),
    ({'confirm_password': 'Mismatch'}, 'confirm_password', 400),
    ({'new_password': 'OldPwd23', 'confirm_password': 'OldPwd23'}, 'new_password', 400),
    ({'new_password': 'short', 'confirm_password': 'short'}, 'new_password', 422),
    ({'new_password': 'a' * 129, 'confirm_password': 'a' * 129}, 'new_password', 422),
])
def test_bad_password_input_never_changes_password(password_app, overrides, field, status):
    client, sessions, tokens, user_id, *_ = password_app
    response = change(client, tokens[0], **overrides)
    assert response.status_code == status
    assert any(item['loc'][-1] == field for item in response.json()['detail'])
    with sessions() as db:
        assert auth.verify_password('OldPwd23', db.get(AppUser, user_id).password_hash)
        assert 'password_changed' not in db.scalars(select(LoginSecurityEvent.event_type)).all()


def test_current_password_attempts_are_throttled(password_app, monkeypatch):
    client, sessions, tokens, user_id, *_ = password_app
    monkeypatch.setattr(auth_security, 'ACCOUNT_FAILURE_LIMIT', 3)
    assert change(client, tokens[0], current_password='Wrong234').status_code == 400
    assert change(client, tokens[0], current_password='Wrong234').status_code == 400
    response = change(client, tokens[0], current_password='Wrong234')
    assert response.status_code == 429 and int(response.headers['retry-after']) > 0
    assert change(client, tokens[0]).status_code == 429
    with sessions() as db:
        assert auth.verify_password('OldPwd23', db.get(AppUser, user_id).password_hash)


def test_admin_password_reset_also_invalidates_old_tokens(password_app):
    client, sessions, tokens, user_id, *_ = password_app
    with sessions() as db:
        reset_user_password(db, user_id, 'AdminPwd8')
    assert client.get('/auth/session', headers={'Authorization': 'Bearer ' + tokens[0]}).status_code == 401


def test_open_notification_connection_rejects_token_after_password_change(password_app):
    client, sessions, tokens, user_id, *_ = password_app
    with client.websocket_connect('/notifications/ws?token=' + tokens[0]) as socket:
        assert socket.receive_json()['type'] == 'snapshot'
        socket.send_text('ping')
        assert socket.receive_json()['type'] == 'pong'
        with sessions() as db:
            reset_user_password(db, user_id, 'AdminPwd8')
        socket.send_text('ping')
        with pytest.raises(WebSocketDisconnect) as error:
            socket.receive_json()
        assert error.value.code == 1008


def test_legacy_token_and_disabled_user_cannot_change_password(password_app):
    client, sessions, tokens, user_id, *_ = password_app
    legacy = auth.create_access_token({'sub': 'password-user', 'user_id': str(user_id)})
    assert change(client, legacy).status_code == 401
    with sessions() as db:
        db.get(AppUser, user_id).is_active = False; db.commit()
    assert change(client, tokens[0]).status_code == 401
    assert client.put('/auth/password', json={}).status_code == 401


@pytest.mark.parametrize('oauth', [False, True])
def test_both_login_routes_issue_password_version(password_app, oauth):
    client, *_ = password_app
    data = {'username': 'password-user', 'password': 'OldPwd23'}
    response = client.post('/auth/login', data=data) if oauth else client.post('/auth/login/json', json=data)
    assert response.status_code == 200
    token = response.json()['access_token']
    assert client.get('/auth/session', headers={'Authorization': 'Bearer ' + token}).status_code == 200
