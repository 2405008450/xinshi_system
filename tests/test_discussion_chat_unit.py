"""独立讨论使用内存数据库验证，不访问云端、不发送真实消息。"""
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_chat_session_folders_unit import local_db, actor
from discussion_chat_models import DiscussionMessage as Message, DiscussionMember as Member
import discussion_chat_service as service
from routers.discussion_chat import MessageCreate, PreferenceWrite, recall


@pytest.fixture
def rooms(local_db, monkeypatch):
    engine = local_db.get_bind()
    Message.__table__.create(engine)
    Member.__table__.create(engine)
    monkeypatch.setattr(service, 'publish', lambda db: None)
    monkeypatch.setattr(service, 'get_user_permission_codes', lambda db, uid: ['talents:read'])
    monkeypatch.setattr(service, 'user_has_permission', lambda db, uid, code: False)
    return local_db, UUID(service.room_specs(local_db)[0]['id']), actor()


def send(db, room, user, text='讨论内容', **kwargs):
    return service.send(db, user, room, MessageCreate(content=text, client_message_id=uuid4(), **kwargs))


def test_catalog_six_real_discussion_sessions_and_unmigrated_fallback(rooms):
    db, room, user = rooms
    rows = service.catalog(db, user)
    assert [row['title'] for row in rows] == ['平台讨论', '资源讨论', '企微管理', '发布需求', '高校渠道', '其他渠道']
    assert all(row['kind'] == 'discussion' and row['storage_ready'] for row in rows)
    Message.__table__.drop(db.get_bind())
    assert all(not row['storage_ready'] for row in service.catalog(db, user))
    with pytest.raises(HTTPException) as unavailable:
        service.messages(db, user, room)
    assert unavailable.value.status_code == 503


def test_permissions_account_state_and_room_boundary(rooms, monkeypatch):
    db, room, user = rooms
    monkeypatch.setattr(service, 'get_user_permission_codes', lambda db, uid: [])
    assert service.catalog(db, actor('other')) == []
    for denied in (actor('other'), actor(active=False)):
        with pytest.raises(HTTPException) as error:
            service.messages(db, denied, room)
        assert error.value.status_code == 403
    with pytest.raises(HTTPException) as missing:
        service.messages(db, user, uuid4())
    assert missing.value.status_code == 404


def test_idempotent_send_snapshot_timezone_and_stable_pagination(rooms):
    db, room, user = rooms
    payload = MessageCreate(content='  平台问题  ', client_message_id=uuid4())
    first = service.send(db, user, room, payload)
    assert first['id'] == service.send(db, user, room, payload)['id']
    assert first['content'] == '平台问题' and first['created_at'].endswith('+08:00')
    assert db.query(Message).count() == 1
    for number in range(5):
        send(db, room, user, f'后续{number}')
    last = service.messages(db, user, room, limit=2)
    assert last['has_more'] and len(last['items']) == 2
    earlier = service.messages(db, user, room, before=int(last['items'][0]['id']), limit=2)
    assert max(int(row['id']) for row in earlier['items']) < int(last['items'][0]['id'])
    assert len(service.messages(db, user, room, after=int(first['id']))['items']) == 5


def test_reply_read_and_recall_stay_in_the_current_room(rooms):
    db, room, user = rooms
    peer = actor('peer')
    first = send(db, room, peer, '原消息')
    reply = send(db, room, user, '回复', reply_to_id=int(first['id']))
    assert reply['reply']['id'] == first['id']
    other = UUID(service.room_specs(db)[1]['id'])
    with pytest.raises(HTTPException):
        send(db, other, user, reply_to_id=int(first['id']))
    assert next(row for row in service.catalog(db, user) if row['project_id'] == str(room))['unread'] == 1
    service.preferences(db, user, room, PreferenceWrite(read_message_id=int(reply['id']), pinned=True))
    result = service.preferences(db, user, room, PreferenceWrite(read_message_id=int(first['id'])))
    assert result['last_read_id'] == reply['id'] and result['pinned']
    with pytest.raises(HTTPException):
        service.preferences(db, user, other, PreferenceWrite(read_message_id=int(first['id'])))
    db.rollback()
    with pytest.raises(HTTPException) as denied:
        recall(room, int(first['id']), db, user)
    assert denied.value.status_code == 403
    recalled = recall(room, int(first['id']), db, peer)
    assert recalled['content'] == '' and recalled['recalled_at'].endswith('+08:00')
    assert service.messages(db, user, room)['items'][1]['reply']['content'] == '消息已撤回'


def test_search_treats_percent_as_literal_and_rejects_sender_spoofing(rooms):
    db, room, user = rooms
    send(db, room, user, '覆盖率100%')
    send(db, room, user, '普通内容')
    assert len(service.messages(db, user, room, keyword='%')['items']) == 1
    for content in ('', '   ', 'x' * 10001):
        with pytest.raises(ValidationError):
            MessageCreate(content=content, client_message_id=uuid4())
    with pytest.raises(ValidationError):
        MessageCreate(content='伪造发送人', client_message_id=uuid4(), sender_id=user.id)
