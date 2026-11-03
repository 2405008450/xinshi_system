"""浏览器推送仅使用隔离 SQLite 和模拟发送，不访问真实推送服务。"""
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from test_chat_participant_access import environment
from models import PushSubscription
from routers import push


@pytest.fixture
def configured(monkeypatch):
    for key in ('VAPID_PUBLIC_KEY', 'VAPID_PRIVATE_KEY', 'VAPID_SUBJECT'):
        monkeypatch.setenv(key, 'isolated-test-value')


def request(**values):
    return push.SubReq(endpoint='https://push.example/subscription', p256dh='test-key', auth='test-auth', **values)


def test_subscription_account_binding_keys_and_delete_isolation(environment, configured):
    db, (owner, other, _) = environment
    req = request()
    push.subscribe(req, db, owner)
    push.subscribe(req, db, owner)
    assert db.query(PushSubscription).count() == 1
    push.unsubscribe(push.EndpointRequest(endpoint=req.endpoint), db, other)
    assert db.query(PushSubscription).count() == 1
    updated = req.model_copy(update={'p256dh': 'new-key', 'auth': 'new-auth'})
    push.subscribe(updated, db, other)
    row = db.query(PushSubscription).one()
    assert (row.user_id, row.p256dh, row.auth) == (other.id, 'new-key', 'new-auth')
    assert PushSubscription.created_at.default.arg(None).utcoffset() == timedelta(hours=8)
    push.unsubscribe(push.EndpointRequest(endpoint=req.endpoint), db, other)
    assert db.query(PushSubscription).count() == 0


def test_missing_configuration_or_table_does_not_break_chat(environment, monkeypatch):
    db, (owner, _, _) = environment
    monkeypatch.delenv('VAPID_PRIVATE_KEY', raising=False)
    monkeypatch.setattr(push, 'schema_ready', lambda *_: pytest.fail('未配置时不查询订阅表'))
    assert push.get_public_key() == {'publicKey': None}
    push.send_push_to_user(db, owner.id, '通知', '内容')
    with pytest.raises(HTTPException) as error:
        push.subscribe(request(), db, owner)
    assert error.value.status_code == 503


def test_missing_table_with_configuration_is_safe(environment, configured, monkeypatch):
    db, (owner, _, _) = environment
    monkeypatch.setattr(push, 'schema_ready', lambda *_: False)
    push.send_push_to_user(db, owner.id, '通知', '内容')
    with pytest.raises(HTTPException) as error:
        push.subscribe(request(), db, owner)
    assert error.value.status_code == 503


@pytest.mark.parametrize('endpoint', ['http://push.example/x', 'https://127.0.0.1/x', 'https://192.168.1.2/x', 'https://localhost/x', 'https://user:password@push.example/x'])
def test_endpoint_validation(endpoint):
    with pytest.raises(ValidationError):
        push.EndpointRequest(endpoint=endpoint)


def test_send_scopes_recipients_expired_endpoints_and_payload(environment, configured, monkeypatch):
    import pywebpush
    from types import SimpleNamespace
    db, (owner, other, _) = environment
    for user in (owner, other):
        db.add(PushSubscription(id=uuid4(), user_id=user.id, endpoint=f'https://push.example/{user.id}', p256dh='key', auth='auth'))
    db.commit()
    sent = []
    monkeypatch.setattr(pywebpush, 'webpush', lambda **kwargs: sent.append(kwargs))
    push.send_push_to_user(db, owner.id, '新消息', '点击查看', '//outside.example')
    assert len(sent) == 1 and sent[0]['subscription_info']['endpoint'].endswith(str(owner.id))
    assert json.loads(sent[0]['data'])['url'] == '/workbench'
    assert sent[0]['vapid_claims']['aud'] == 'https://push.example'
    assert sent[0]['timeout'] == 5
    def expired(**kwargs):
        raise pywebpush.WebPushException('expired', response=SimpleNamespace(status_code=410))
    monkeypatch.setattr(pywebpush, 'webpush', expired)
    push.send_push_to_user(db, owner.id, '新消息', '点击查看')
    assert [row.user_id for row in db.query(PushSubscription)] == [other.id]


def test_routes_require_login_and_migration_is_repeatable(environment):
    from tools.apply_push_subscriptions_migration import apply_migration
    db, _ = environment
    PushSubscription.__table__.drop(db.connection())
    apply_migration(db.connection())
    apply_migration(db.connection())
    assert db.query(PushSubscription).count() == 0
    app = FastAPI()
    app.include_router(push.router)
    client = TestClient(app)
    assert client.post('/push/subscribe', json=request().model_dump()).status_code == 401
