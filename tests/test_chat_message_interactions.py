"""消息回执和引用只在隔离 SQLite 验证，不连接业务数据库。"""
from datetime import datetime
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment, project  # noqa: F401


def setup_messages(environment):
    db, users = environment
    from models import AnnotationChatMember, ChatProjectMessage
    row = project(db, users[0])
    for person in users[:2]:
        db.add(AnnotationChatMember(project_id=row.id, user_id=person.id, following=True, explicit_unfollow=False, last_read_sequence=999))
    original = ChatProjectMessage(id=uuid4(), annotation_project_id=row.id, sender_user_id=users[0].id,
        sender_name=users[0].username, content='原消息', message_type='user', sequence_no=1, created_at=datetime(2026, 10, 22, 10))
    db.add(original); db.commit()
    return db, users, row, original


def test_views_are_explicit_idempotent_and_independent_of_follow_cursor_and_ack(environment, monkeypatch):
    import chat_message_interactions as service
    from chat_message_view_models import ChatMessageView
    from models import AnnotationChatMember, ChatProjectMessageAcknowledgement
    monkeypatch.setattr('notification_ws.broadcast_to_users', lambda *args: None)
    db, (owner, member, outsider), row, message = setup_messages(environment)
    initial = service.stats(db, 'annotation', row.id, owner, [str(message.id)])['items'][0]
    assert initial['seen_count'] == 0  # last_read_sequence=999 不是逐条阅读证据。
    assert initial['recipient_count'] == 1
    service.mark_views(db, 'annotation', row.id, member, [str(message.id), str(message.id)])
    first = db.query(ChatMessageView).one().seen_at
    service.mark_views(db, 'annotation', row.id, member, [str(message.id)])
    assert db.query(ChatMessageView).count() == 1
    assert db.query(ChatMessageView).one().seen_at == first
    assert db.query(ChatProjectMessageAcknowledgement).count() == 0
    item = service.stats(db, 'annotation', row.id, owner, [str(message.id)])['items'][0]
    assert item['seen_count'] == 1
    assert item['seen_users'][0]['id'] == member.id
    assert item['seen_users'][0]['seen_at'].utcoffset().total_seconds() == 8 * 3600
    assert service.stats(db, 'annotation', row.id, member, [str(message.id)])['items'][0]['seen_users'] == []
    service.mark_views(db, 'annotation', row.id, owner, [str(message.id)])
    assert db.query(ChatMessageView).count() == 1  # 自己不计入已读。
    db.delete(db.get(AnnotationChatMember, (row.id, member.id))); db.commit()
    item = service.stats(db, 'annotation', row.id, owner, [str(message.id)])['items'][0]
    assert item['seen_count'] == item['recipient_count'] == 0


def test_member_and_exact_order_guards_cover_stats_views_and_references(environment, monkeypatch):
    import chat_message_interactions as service
    from models import AnnotationChatMember
    monkeypatch.setattr('notification_ws.broadcast_to_users', lambda *args: None)
    db, (owner, member, outsider), row, message = setup_messages(environment)
    for method in (service.stats, service.mark_views):
        with pytest.raises(HTTPException) as denied:
            method(db, 'annotation', row.id, outsider, [str(message.id)])
        assert denied.value.status_code == 404
    with pytest.raises(HTTPException):
        service.references(db, 'annotation', row.id, outsider, str(message.id))
    other = project(db, owner, 'AP-261021-001.001')
    db.add(AnnotationChatMember(project_id=other.id, user_id=owner.id)); db.commit()
    for method in (service.stats, service.mark_views):
        with pytest.raises(HTTPException) as wrong_order:
            method(db, 'annotation', other.id, owner, [str(message.id)])
        assert wrong_order.value.status_code == 404
    with pytest.raises(HTTPException):
        service.references(db, 'annotation', other.id, owner, str(message.id))


def test_all_direct_references_paginate_and_recalled_content_is_hidden(environment):
    import chat_message_interactions as service
    from models import ChatProjectMessage
    db, (owner, member, outsider), row, original = setup_messages(environment)
    for index in range(31):
        db.add(ChatProjectMessage(id=uuid4(), annotation_project_id=row.id, sender_user_id=member.id,
            sender_name=member.username, content=f'引用 {index}', message_type='user', sequence_no=index + 2,
            reply_to_message_id=original.id, created_at=datetime(2026, 10, 22, 11, index)))
    withdrawn = ChatProjectMessage(id=uuid4(), annotation_project_id=row.id, sender_user_id=member.id,
        sender_name=member.username, content='不得泄漏', message_type='user', sequence_no=99,
        reply_to_message_id=original.id, created_at=datetime(2026, 10, 22, 12), recalled_at=datetime(2026, 10, 22, 12, 1))
    db.add(withdrawn); db.commit()
    first = service.references(db, 'annotation', row.id, owner, str(original.id), 0, 20)
    second = service.references(db, 'annotation', row.id, owner, str(original.id), 20, 20)
    assert first['total'] == 31 and first['has_more']
    assert len(second['items']) == 11 and not second['has_more']
    assert not set(item['id'] for item in first['items']) & set(item['id'] for item in second['items'])
    own = service.stats(db, 'annotation', row.id, member, [str(original.id)])['items'][0]
    assert own['reply_count'] == 31 and own['has_replied']
    original.recalled_at = datetime(2026, 10, 22, 12, 2); db.commit()
    result = service.references(db, 'annotation', row.id, owner, str(original.id))
    assert result['original']['content'] == '消息已撤回'
    assert result['items'] == []


def test_reference_window_follows_original_and_contains_all_branches(environment):
    import chat_message_interactions as service
    from models import ChatProjectMessage
    db,(owner,member,_),project_row,original=setup_messages(environment)
    def reply(parent,minute,content):
        row=ChatProjectMessage(id=uuid4(),annotation_project_id=project_row.id,sender_user_id=member.id,
            sender_name=member.username,content=content,message_type='user',sequence_no=minute+2,
            reply_to_message_id=parent.id,created_at=datetime(2026,10,22,11,minute))
        db.add(row);db.flush();return row
    first=reply(original,0,'直接引用一')
    nested=reply(first,1,'继续引用一')
    deepest=reply(nested,2,'再次引用')
    sibling=reply(original,3,'直接引用二')
    db.commit()
    result=service.references(db,'annotation',project_row.id,owner,str(nested.id),0,2)
    assert result['original']['id']==str(original.id)
    assert result['selected_message_id']==str(nested.id)
    assert result['total']==4 and result['direct_count']==2 and result['has_more']
    second=service.references(db,'annotation',project_row.id,owner,str(nested.id),2,2)
    rows={row['id']:row for row in result['items']+second['items']}
    assert set(rows)=={str(row.id) for row in [first,nested,deepest,sibling]}
    assert rows[str(nested.id)]['parent_id']==str(first.id)
    assert rows[str(nested.id)]['parent_reference_number']==rows[str(first.id)]['reference_number']
    assert rows[str(deepest.id)]['depth']==3
    assert rows[str(deepest.id)]['ancestor_ids']==[str(first.id),str(nested.id)]
    first.recalled_at=datetime(2026,10,22,12);db.commit()
    safe=service.references(db,'annotation',project_row.id,owner,str(original.id))
    nested_safe=next(row for row in safe['items'] if row['id']==str(nested.id))
    assert nested_safe['parent']['content']=='消息已撤回'


def test_missing_migration_does_not_break_replies_or_fabricate_reads_and_migration_is_repeatable(environment):
    import chat_message_interactions as service
    from chat_message_view_models import ChatMessageView
    from tools.apply_chat_message_views_migration import apply_migration
    db, (owner, member, outsider), row, message = setup_messages(environment)
    ChatMessageView.__table__.drop(db.connection())
    assert service.stats(db, 'annotation', row.id, owner, [str(message.id)])['views_available'] is False
    assert service.references(db, 'annotation', row.id, owner, str(message.id))['original']['content'] == '原消息'
    with pytest.raises(HTTPException) as disabled:
        service.mark_views(db, 'annotation', row.id, member, [str(message.id)])
    assert disabled.value.status_code == 503
    apply_migration(db.connection()); apply_migration(db.connection())
    assert db.query(ChatMessageView).count() == 0
    assert service.stats(db, 'annotation', row.id, owner, [str(message.id)])['views_available'] is True
