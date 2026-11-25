"""已发送消息编辑能力单元测试：使用隔离内存库，覆盖策略、讨论组、标注/私聊/项目沟通核心逻辑。"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from chat_recall_policy import can_edit_own
from chat_time import BUSINESS_TIMEZONE
import annotation_chat_service
import direct_chat_service
import discussion_chat_service
from discussion_chat_models import DiscussionMember, DiscussionMessage
from models import (
    AppUser,
    ChatDirectConversation,
    ChatDirectMember,
    ChatProjectAttachment,
    ChatProjectMessage,
    ChatProjectMessageAttachment,
    ChatProjectMessageFavorite,
    ChatProjectMention,
    ChatProjectMessageAcknowledgement,
)
from routers.discussion_chat import MessageCreate, MessageEdit, edit as discussion_edit, recall as discussion_recall
from schemas import ProjectChatMessageEditRequest
from test_chat_session_folders_unit import actor, local_db


def test_can_edit_own_one_hour_window():
    uid = uuid4()
    other = uuid4()
    base = datetime(2026, 11, 23, 14, 0, 0, tzinfo=BUSINESS_TIMEZONE)
    assert can_edit_own(uid, uid, base, None, current=base + timedelta(minutes=59)) is True
    assert can_edit_own(uid, uid, base, None, current=base + timedelta(hours=1)) is True
    assert can_edit_own(uid, uid, base, None, current=base + timedelta(hours=1, seconds=1)) is False
    assert can_edit_own(uid, other, base, None, current=base + timedelta(minutes=5)) is False
    assert can_edit_own(uid, uid, base, base + timedelta(minutes=1), current=base + timedelta(minutes=5)) is False


def test_annotation_can_edit_excludes_system_and_creation_card():
    uid = uuid4()
    now_naive = datetime(2026, 11, 23, 14, 10, 0)
    created = datetime(2026, 11, 23, 14, 0, 0)
    normal = SimpleNamespace(
        message_type='user',
        sender_user_id=uid,
        created_at=created,
        recalled_at=None,
        content_json=None,
    )
    system_msg = SimpleNamespace(
        message_type='handover',
        sender_user_id=uid,
        created_at=created,
        recalled_at=None,
        content_json=None,
    )
    card_msg = SimpleNamespace(
        message_type='user',
        sender_user_id=uid,
        created_at=created,
        recalled_at=None,
        content_json={'type': 'annotation_creation'},
    )
    assert annotation_chat_service.can_edit(normal, uid, now=now_naive) is True
    assert annotation_chat_service.can_edit(system_msg, uid, now=now_naive) is False
    assert annotation_chat_service.can_edit(card_msg, uid, now=now_naive) is False


@pytest.fixture
def discussion_env(local_db, monkeypatch):
    import chat_message_notifications
    monkeypatch.setattr(chat_message_notifications, 'ordinary_notifications', lambda *a, **kw: [])
    monkeypatch.setattr(chat_message_notifications, 'settle_notifications', lambda *a, **kw: None)
    engine = local_db.get_bind()
    DiscussionMessage.__table__.create(engine, checkfirst=True)
    DiscussionMember.__table__.create(engine, checkfirst=True)
    published = []
    monkeypatch.setattr(discussion_chat_service, 'publish', lambda *args, **kwargs: published.append(True))
    monkeypatch.setattr(discussion_chat_service, 'get_user_permission_codes', lambda db, uid: ['talents:read'])
    monkeypatch.setattr(discussion_chat_service, 'user_has_permission', lambda db, uid, code: False)
    user = actor('alice')
    other = actor('bob')
    room_id = UUID(discussion_chat_service.room_specs(local_db)[0]['id'])
    for person in (user, other):
        local_db.add(DiscussionMember(room_id=room_id, user_id=person.id, last_read_id=0, pinned=False, starred=False))
    local_db.flush()
    return local_db, room_id, user, other, published


def test_discussion_edit_preserves_reply_updates_quote_and_enforces_rules(discussion_env):
    db, room_id, alice, bob, published = discussion_env
    first = discussion_chat_service.send(
        db, alice, room_id, MessageCreate(content='原始需求说明', client_message_id=uuid4())
    )
    reply = discussion_chat_service.send(
        db, alice, room_id, MessageCreate(content='补充一条引用回复', client_message_id=uuid4(), reply_to_id=int(first['id']))
    )
    assert first['can_edit'] is True
    assert first['edited_at'] is None

    # 编辑被引用消息，检查编辑时间及引用摘要同步更新
    edited_first = discussion_edit(room_id, int(first['id']), MessageEdit(content='更新后的需求说明'), db=db, user=alice)
    assert edited_first['content'] == '更新后的需求说明'
    assert edited_first['edited_at'] is not None
    assert '+08:00' in edited_first['edited_at']
    assert len(published) >= 3

    # 编辑带引用的回复，原 reply 必须保留
    edited_reply = discussion_edit(room_id, int(reply['id']), MessageEdit(content='修改后的补充回复'), db=db, user=alice)
    assert edited_reply['content'] == '修改后的补充回复'
    assert edited_reply['reply']['id'] == first['id']
    assert edited_reply['reply']['content'] == '更新后的需求说明'

    # 他人不能编辑
    with pytest.raises(HTTPException) as forbidden:
        discussion_edit(room_id, int(first['id']), MessageEdit(content='篡改'), db=db, user=bob)
    assert forbidden.value.status_code == 403

    # 超过 1 小时不能编辑
    row = db.get(DiscussionMessage, int(first['id']))
    row.created_at = row.created_at - timedelta(hours=2)
    db.commit()
    with pytest.raises(HTTPException) as expired:
        discussion_edit(room_id, int(first['id']), MessageEdit(content='超时修改'), db=db, user=alice)
    assert expired.value.status_code == 403

    # 已撤回消息不能编辑
    discussion_recall(room_id, int(reply['id']), db=db, user=alice)
    with pytest.raises(HTTPException) as recalled:
        discussion_edit(room_id, int(reply['id']), MessageEdit(content='撤回后修改'), db=db, user=alice)
    assert recalled.value.status_code == 409


def test_direct_and_annotation_edit_preserve_reply_and_attachments(monkeypatch):
    alice_id = uuid4()
    bob_id = uuid4()
    conv_id = uuid4()
    parent_id = uuid4()
    child_id = uuid4()
    alice = SimpleNamespace(id=alice_id, full_name='Alice', username='alice', is_active=True)
    bob = SimpleNamespace(id=bob_id, full_name='Bob', username='bob', is_active=True)
    now_naive = datetime.now(BUSINESS_TIMEZONE).replace(tzinfo=None)

    child = SimpleNamespace(
        id=child_id,
        direct_conversation_id=conv_id,
        annotation_project_id=conv_id,
        sender_user_id=alice_id,
        sender_name='Alice',
        content='带附件和引用的消息',
        content_json=None,
        message_type='user',
        reply_to_message_id=parent_id,
        attachment_links=[SimpleNamespace(attachment_id=uuid4())],
        created_at=now_naive,
        updated_at=now_naive,
        recalled_at=None,
        edited_at=None,
    )
    parent = SimpleNamespace(
        id=parent_id,
        direct_conversation_id=conv_id,
        annotation_project_id=conv_id,
        sender_user_id=bob_id,
        sender_name='Bob',
        content='无附件消息',
        content_json=None,
        message_type='user',
        reply_to_message_id=None,
        attachment_links=[],
        created_at=now_naive,
        updated_at=now_naive,
        recalled_at=None,
        edited_at=None,
    )

    class FakeQuery:
        def __init__(self, row):
            self._row = row

        def filter(self, *args, **kwargs):
            return self

        def filter_by(self, **kwargs):
            return self

        def with_for_update(self):
            return self

        def populate_existing(self):
            return self

        def first(self):
            return self._row

    class FakeDB:
        def __init__(self):
            self.commits = 0

        def commit(self):
            self.commits += 1

    db = FakeDB()
    events = []
    monkeypatch.setattr(direct_chat_service, 'require_project', lambda *a, **k: SimpleNamespace(id=conv_id))
    monkeypatch.setattr(direct_chat_service, 'publish', lambda d, pid, kind='changed', mid=None: events.append(('direct', pid, kind, mid)))
    monkeypatch.setattr(annotation_chat_service, 'require_project', lambda *a, **k: SimpleNamespace(id=conv_id))
    monkeypatch.setattr(annotation_chat_service, 'publish', lambda d, pid, kind='changed', mid=None: events.append(('annotation', pid, kind, mid)))

    # 1. 私聊：编辑成功，保留原引用和原附件
    monkeypatch.setattr(direct_chat_service, 'message_query', lambda *a, **k: FakeQuery(child))
    updated = direct_chat_service.edit_message(db, conv_id, child_id, alice, ProjectChatMessageEditRequest(content='编辑后的私聊内容'))
    assert updated.content == '编辑后的私聊内容'
    assert updated.edited_at is not None
    assert updated.reply_to_message_id == parent_id
    assert len(updated.attachment_links) == 1
    assert events[-1] == ('direct', conv_id, 'edit', child_id)

    # 2. 私聊：带附件时允许正文留空
    cleared = direct_chat_service.edit_message(db, conv_id, child_id, alice, ProjectChatMessageEditRequest(content='   '))
    assert cleared.content == ''
    assert len(cleared.attachment_links) == 1

    # 3. 标注群聊：无附件不允许正文留空
    monkeypatch.setattr(annotation_chat_service, 'message_query', lambda *a, **k: FakeQuery(parent))
    with pytest.raises(HTTPException) as empty_err:
        annotation_chat_service.edit_message(db, conv_id, parent_id, bob, ProjectChatMessageEditRequest(content='   '))
    assert empty_err.value.status_code == 422

    # 4. 标注群聊：正常编辑触发 edit 推送
    edited_ann = annotation_chat_service.edit_message(db, conv_id, parent_id, bob, ProjectChatMessageEditRequest(content='标注新内容'))
    assert edited_ann.content == '标注新内容'
    assert edited_ann.edited_at is not None
    assert events[-1] == ('annotation', conv_id, 'edit', parent_id)

    # 5. 超 1 小时不可编辑
    parent.created_at = now_naive - timedelta(hours=2)
    with pytest.raises(HTTPException) as timeout_err:
        annotation_chat_service.edit_message(db, conv_id, parent_id, bob, ProjectChatMessageEditRequest(content='超时'))
    assert timeout_err.value.status_code == 403
