from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from discussion_chat_files import file_ids, validate_files


def test_discussion_files_are_owned_and_bound_to_room():
    room, other_room, id, owner = uuid4(), uuid4(), uuid4(), uuid4()
    row = SimpleNamespace(storage_name=f'discussion_{room.hex}_{id.hex}.pdf', uploaded_by=owner)
    db = SimpleNamespace(get=lambda model, key: row if key == id else None)
    content = f'[附件](discussion-file://{id})'
    assert file_ids(content + content) == [id]
    validate_files(db, SimpleNamespace(id=owner), room, content)
    with pytest.raises(HTTPException) as error:
        validate_files(db, SimpleNamespace(id=uuid4()), room, content)
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        validate_files(db, SimpleNamespace(id=owner), other_room, content)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException):
        validate_files(db, SimpleNamespace(id=owner), room, f'[附件](discussion-file://{uuid4()})')


def test_discussion_file_count_and_invalid_ids():
    db = SimpleNamespace(get=lambda *args: pytest.fail('超过限制时不应查询附件'))
    with pytest.raises(HTTPException) as error:
        validate_files(db, SimpleNamespace(id=uuid4()), uuid4(), '\n'.join(f'[附件](discussion-file://{uuid4()})' for _ in range(10)))
    assert error.value.status_code == 422
    with pytest.raises(HTTPException):
        file_ids('[附件](discussion-file://' + '-' * 36 + ')')


def test_download_requires_room_access_and_a_visible_message(monkeypatch):
    import asyncio
    from routers import discussion_chat as api
    room, id, owner = uuid4(), uuid4(), uuid4()
    row = SimpleNamespace(storage_name=f'discussion_{room.hex}_{id.hex}.pdf', uploaded_by=owner, original_name='方案.pdf', file_size=42)
    query = SimpleNamespace(filter=lambda *args: query, first=lambda: None)
    db = SimpleNamespace(get=lambda *args: row, query=lambda *args: query)
    allowed = []
    monkeypatch.setattr(api.service, 'require_room', lambda *args: allowed.append(args))
    assert asyncio.run(api.read_file(room, id, None, True, db, SimpleNamespace(id=owner))) == {'name': '方案.pdf', 'size': 42}
    with pytest.raises(HTTPException) as error:
        asyncio.run(api.read_file(room, id, None, True, db, SimpleNamespace(id=uuid4())))
    assert error.value.status_code == 404
    query.first = lambda: (1,)
    assert asyncio.run(api.read_file(room, id, None, True, db, SimpleNamespace(id=uuid4())))['name'] == '方案.pdf'
    assert len(allowed) == 3
