"""居家办公人员登记及权限，使用隔离 SQLite。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from uuid import uuid4

from database import get_db
from office_management import OfficeRemoteWorker, router
from routers import auth
from test_office_management import offices  # noqa: F401
from test_chat_participant_access import environment  # noqa: F401
from tools.apply_office_remote_worker_migration import apply_migration


def test_remote_worker_registration_and_permissions(offices, monkeypatch):
    db, (admin, reader, person) = offices
    person.is_active = False
    db.commit()
    OfficeRemoteWorker.__table__.drop(db.connection())
    apply_migration(db.connection())
    apply_migration(db.connection())
    db.commit()

    permissions = {admin.id: ['system:organization:write'], reader.id: ['system:users:read']}
    monkeypatch.setattr(auth, 'get_user_permission_codes', lambda db, uid: permissions.get(uid, []))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: admin
    path = '/office-management/remote-workers'
    data = {'city': ' 杭州 ', 'user_id': str(person.id)}
    with TestClient(app) as client:
        options = client.get(f'{path}/people').json()['items']
        assert {row['id'] for row in options} == {str(user.id) for user in (admin, reader, person)}
        assert client.post(path, json={**data, 'user_id': str(uuid4())}).status_code == 422
        assert client.post(path, json={**data, 'city': '  '}).status_code == 422
        created = client.post(path, json=data)
        assert created.status_code == 200
        record_id = created.json()['id']
        row, = client.get(path).json()['items']
        assert row['city'] == '杭州' and not row['is_active']
        assert client.post(path, json=data).status_code == 409
        details = f'{path}/{record_id}'
        assert client.put(details, json={**data, 'city': '苏州', 'revision': 1}).status_code == 200
        assert client.delete(details, params={'revision': 1}).status_code == 409

        app.dependency_overrides[auth.get_current_user] = lambda: reader
        assert client.get(path).json()['items'][0]['city'] == '苏州'
        assert client.get(f'{path}/people').status_code == 403
        assert client.delete(details, params={'revision': 2}).status_code == 403
        app.dependency_overrides[auth.get_current_user] = lambda: person
        assert client.get(path).status_code == 403

        app.dependency_overrides[auth.get_current_user] = lambda: admin
        assert client.delete(details, params={'revision': 2}).status_code == 200
        assert client.get(path).json()['items'] == []
