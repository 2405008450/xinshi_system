from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from tests.test_chat_participant_access import environment
from database import get_db
from models import Client
from routers import auth
import customer_annotation_rates as rates
from tools.apply_customer_annotation_rates_migration import apply_migration


@pytest.fixture
def context(environment, monkeypatch):
    db, users = environment
    # 重建此新表以保留真实唯一约束；其他业务表仍使用隔离 SQLite 夹具。
    rates.CustomerAnnotationRate.__table__.drop(db.connection())
    before = set(inspect(db.connection()).get_table_names())
    apply_migration(db.connection()); apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names()) - before == {'customer_annotation_rate'}
    clients = [Client(id=uuid4(), client_code=f'CL-{i}', client_name='测试', client_short_name='测试') for i in range(2)]
    db.add_all(clients); db.commit()
    app = FastAPI(); app.include_router(rates.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: users[0]
    granted = {'clients:read', 'clients:write'}
    monkeypatch.setattr(auth, 'user_has_permission', lambda db, uid, code: code in granted)
    with TestClient(app) as http:
        yield http, clients, granted, db


def payload(**extra):
    return dict(project_type='audio_annotation', amount='0.123456', unit='minute', **extra)


def test_crud_decimal_currency_default_customer_isolation_and_revision(context):
    http, clients, _, db = context
    base = f'/clients/{clients[0].id}/annotation-rates'
    other = f'/clients/{clients[1].id}/annotation-rates'
    result = http.post(base, json=payload())
    assert result.status_code == 201, result.text
    row = result.json()
    assert row['currency'] == 'CNY' and row['amount'] == '0.123456'
    assert row['updated_at'].endswith('+08:00')
    assert http.get(base).json()['items'] == [row]
    assert http.get(other).json() == {'items': []}
    path = f"{base}/{row['id']}"
    assert http.put(f"{other}/{row['id']}", json={**payload(), 'revision': 1}).status_code == 404
    duplicate = http.post(base, json=payload())
    assert duplicate.status_code == 409
    result = http.put(path, json={**payload(currency='USD'), 'amount': '12.345678', 'revision': 1})
    assert result.status_code == 200 and result.json()['revision'] == 2
    assert Decimal(result.json()['amount']) == Decimal('12.345678')
    assert http.put(path, json={**payload(), 'revision': 1}).status_code == 409
    assert http.delete(path, params={'revision': 1}).status_code == 409
    assert http.delete(f"{other}/{row['id']}", params={'revision': 2}).status_code == 404
    assert http.delete(path, params={'revision': 2}).status_code == 204
    assert http.get(base).json()['items'] == []


@pytest.mark.parametrize('field,value', [
    ('project_type', 'invalid'), ('currency', 'bad'), ('unit', 'invalid'),
    ('amount', '0'), ('amount', '-1'), ('amount', '0.1234567'), ('amount', 'NaN'),
])
def test_invalid_input(context, field, value):
    http, clients, _, _ = context
    body = payload(); body[field] = value
    assert http.post(f'/clients/{clients[0].id}/annotation-rates', json=body).status_code == 422


def test_permissions_and_missing_client(context):
    http, clients, granted, _ = context
    base = f'/clients/{clients[0].id}/annotation-rates'
    granted.remove('clients:write')
    assert http.post(base, json=payload()).status_code == 403
    assert http.get(base).status_code == 200
    granted.remove('clients:read')
    assert http.get(base).status_code == 403
    granted.update({'clients:read', 'clients:write'})
    missing = f'/clients/{uuid4()}/annotation-rates'
    assert http.get(missing).status_code == 404
    assert http.post(missing, json=payload()).status_code == 404
