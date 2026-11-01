"""简短记录隔离测试，只使用内存 SQLite。"""
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect

from tests.test_chat_participant_access import environment
from models import TranslationProject
from translation_project_notes import NoteCreate, TranslationProjectNote, add_note, list_notes, router


def project(db):
    row = TranslationProject(id=uuid4(), order_no='TP-NOTE-TEST', project_name='简短记录隔离测试',
                             updated_at=datetime(2026, 10, 31, 10))
    db.add(row); db.commit()
    return row


def test_append_keeps_text_actor_time_and_does_not_change_project(environment):
    db, (owner, member, _) = environment
    row = project(db)
    first = add_note(db, row.id, NoteCreate(content='  客户已确认术语  ', request_id=uuid4()), owner)
    add_note(db, row.id, NoteCreate(content='等待新文件', request_id=uuid4()), member)
    owner.full_name = '改名后'; db.commit()
    result = list_notes(db, row.id)
    assert result['total'] == 2
    saved = next(item for item in result['items'] if item['id'] == first['id'])
    assert saved['content'] == '客户已确认术语'
    assert saved['actor_name'] == saved['actor_username'] == 'owner'
    assert saved['created_at'].endswith('+08:00')
    assert row.updated_at == datetime(2026, 10, 31, 10)


def test_retry_is_idempotent_and_reused_request_cannot_change_record(environment):
    db, (owner, member, _) = environment
    row = project(db); key = uuid4()
    payload = NoteCreate(content='测试重试', request_id=key)
    assert add_note(db, row.id, payload, owner)['id'] == add_note(db, row.id, payload, owner)['id']
    for changed, actor in [(payload, member), (NoteCreate(content='改写旧记录', request_id=key), owner)]:
        with pytest.raises(HTTPException) as error:
            add_note(db, row.id, changed, actor)
        assert error.value.status_code == 409
    assert db.query(TranslationProjectNote).count() == 1


@pytest.mark.parametrize('content', ['', '   ', '字'*201])
def test_empty_and_overlong_text_rejected(content):
    with pytest.raises(ValidationError):
        NoteCreate(content=content, request_id=uuid4())


def test_pagination_and_missing_project(environment):
    db, (owner, _, _) = environment
    row = project(db)
    for index in range(12):
        add_note(db, row.id, NoteCreate(content=f'第{index}条', request_id=uuid4()), owner)
    first = list_notes(db, row.id, 0, 10); second = list_notes(db, row.id, 10, 10)
    assert first['total'] == second['total'] == 12
    assert len(first['items']) == 10 and len(second['items']) == 2
    assert not {r['id'] for r in first['items']} & {r['id'] for r in second['items']}
    with pytest.raises(HTTPException) as error:
        add_note(db, uuid4(), NoteCreate(content='无效项目', request_id=uuid4()), owner)
    assert error.value.status_code == 404


def test_router_permissions_and_server_owned_metadata(environment, monkeypatch):
    from database import get_db
    import routers.auth as auth
    db, (owner, _, _) = environment
    row = project(db)
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: owner
    permissions = {'projects:read'}
    monkeypatch.setattr(auth, 'user_has_permission', lambda db, uid, code: code in permissions)
    with TestClient(app) as client:
        url = f'/projects/translation/{row.id}/short-notes'
        assert client.get(url).status_code == 200
        body = {'content': '权限验证', 'request_id': str(uuid4())}
        assert client.post(url, json=body).status_code == 403
        permissions.add('projects:write')
        assert client.post(url, json={**body, 'actor_name': '冒充人员'}).status_code == 422
        assert client.post(url, json=body).json()['actor_name'] == 'owner'
        assert client.patch(url, json=body).status_code == 405


def test_migration_repeatable_new_table_only():
    from tools.apply_translation_project_note_migration import apply_migration
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        apply_migration(connection); apply_migration(connection)
        assert inspect(connection).get_table_names() == ['translation_project_note']
    engine.dispose()
