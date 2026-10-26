"""隔离数据库验证跨会话搜索及自建会话的访问边界。"""
from datetime import datetime
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment, project  # noqa: F401


def test_search_all_kinds_membership_recall_keywords_and_paging(environment, monkeypatch):
    db, (owner, member, outsider) = environment
    from models import (AnnotationChatMember, ChatProjectMessage, TranslationProject,
                        ChatProjectMemberPref, ChatProjectEnabled, ChatDirectConversation)
    from discussion_chat_models import DiscussionMember, DiscussionMessage
    from chat_session_category_models import ChatSessionCategory, ChatSessionCategoryFolder
    from chat_session_category_service import BUILTIN_FOLDERS
    from chat_global_search import search_messages
    monkeypatch.setattr('chat_global_search.user_has_permission', lambda *args: True)
    parent = project(db, owner)
    db.add(AnnotationChatMember(project_id=parent.id, user_id=owner.id))
    translated = TranslationProject(id=uuid4(), order_no='TR-SEARCH', project_name='项目')
    db.add(translated)
    db.add(ChatProjectMemberPref(project_id=translated.id, user_id=owner.id))
    db.add(ChatProjectEnabled(id=uuid4(), project_id=translated.id, enabled=True))
    low, high = sorted((owner.id, member.id))
    direct = ChatDirectConversation(id=uuid4(), user_low_id=low, user_high_id=high)
    db.add(direct)
    hidden_low, hidden_high = sorted((member.id, outsider.id))
    hidden = ChatDirectConversation(id=uuid4(), user_low_id=hidden_low, user_high_id=hidden_high)
    db.add(hidden)
    room = ChatSessionCategory(id=uuid4(), name='自建群聊', updated_by=owner.id)
    db.add(room)
    db.add(ChatSessionCategoryFolder(category_id=room.id, parent_key=next(row['id'] for row in BUILTIN_FOLDERS if row['ruleKey'] == 'translation')))
    db.add(DiscussionMember(room_id=room.id, user_id=owner.id))
    for seq, scope in enumerate([{'annotation_project_id': parent.id}, {'project_id': translated.id},
                                {'direct_conversation_id': direct.id}, {'direct_conversation_id': hidden.id}], 1):
        db.add(ChatProjectMessage(id=uuid4(), sender_user_id=owner.id, sender_name='发送人', content='BB AA 100%_x',
            message_type='user', sequence_no=seq, created_at=datetime(2026, 10, 24, 12, seq), **scope))
    db.add(ChatProjectMessage(id=uuid4(), annotation_project_id=parent.id, sender_name='发送人', content='AA BB',
        message_type='user', sequence_no=9, created_at=datetime(2026, 10, 24, 13), recalled_at=datetime(2026, 10, 24, 14)))
    db.add(DiscussionMessage(id=1, room_id=room.id, sender_id=owner.id, sender_name='发送人', client_message_id=uuid4(),
        content='AA BB 100%_x', created_at=datetime(2026, 10, 24, 12, 5)))
    db.commit()
    result = search_messages(db, owner, 'AA BB')
    assert result['total'] == 4
    assert {item['project_type'] for item in result['items']} == {'annotation', 'translation', 'direct', 'discussion'}
    first = search_messages(db, owner, 'BB AA', limit=2)
    second = search_messages(db, owner, 'BB AA', offset=2, limit=2)
    assert first['has_more'] and not second['has_more']
    assert {item['key'] for item in first['items']}.isdisjoint(item['key'] for item in second['items'])
    assert search_messages(db, owner, '100%_x')['total'] == 4
    assert search_messages(db, owner, '100%_missing')['total'] == 0
    assert search_messages(db, owner, 'AA missing')['total'] == 0
    assert search_messages(db, owner, '自建群聊')['total'] == 0  # 会话名称由原搜索模式查询。
    assert search_messages(db, outsider, 'AA')['total'] == 1  # 仅自己的私聊。
    outsider.is_active = False
    assert search_messages(db, outsider, 'AA')['total'] == 0
    monkeypatch.setattr('chat_global_search.user_has_permission', lambda *args: False)
    assert 'translation' not in {row['project_type'] for row in search_messages(db, owner, 'AA')['items']}


def test_generic_creation_rename_delete_same_manager_permission(environment):
    db, (owner, member, outsider) = environment
    from routers.chat_session_categories import CategoryCreate, CategoryUpdate, create, update
    from routers.discussion_chat import DiscussionNameWrite, rename
    import discussion_chat_service as service
    from chat_session_category_service import BUILTIN_FOLDERS
    root = next(row['id'] for row in BUILTIN_FOLDERS if row['ruleKey'] == 'translation')
    from uuid import UUID
    payload = CategoryCreate(name='新群聊', parent_key=UUID(root))
    with pytest.raises(HTTPException) as denied:
        create(payload, db, member)
    assert denied.value.status_code == 403
    row = create(payload, db, owner)
    room_id = UUID(row['id'])
    assert row['is_conversation']
    assert service.require_room(db, owner, room_id)['name'] == '新群聊'
    with pytest.raises(HTTPException):
        service.require_room(db, outsider, room_id)
    renamed = rename(room_id, DiscussionNameWrite(name='改名群聊', revision=1), db, owner)
    assert renamed['parent_key'] == root
    with pytest.raises(HTTPException) as denied:
        update(room_id, CategoryUpdate(active=False, revision=2), db, member)
    assert denied.value.status_code == 403
    update(room_id, CategoryUpdate(active=False, revision=2), db, owner)
    assert service.catalog(db, owner) == []
    with pytest.raises(HTTPException):
        service.require_room(db, owner, room_id)
