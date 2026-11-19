"""只使用隔离 SQLite 验证目录窗口、未读保留和历史权限。"""
from datetime import timedelta
from uuid import uuid4

from test_chat_participant_access import environment, project


def test_recent_catalog_preserves_old_unread_pinned_and_starred(environment):
    from business_time import business_now
    from models import AnnotationChatMember, ChatProjectMessage, ChatProjectMessageAcknowledgement
    from routers.chat_sessions import sessions

    db, (owner, member, outsider) = environment
    expected = set()
    historical = set()
    for index, label in enumerate(['近期', '历史已读', '历史未读', '历史已确认', '置顶', '特别关注', '空会话']):
        row = project(db, owner, f'AP-WINDOW-{index}')
        row.project_name = label
        sequence = index + 1
        db.add(AnnotationChatMember(project_id=row.id, user_id=member.id, following=True,
            last_read_sequence=sequence if label in ['近期', '历史已读'] else 0,
            pinned=label == '置顶', starred=label == '特别关注'))
        if label != '空会话':
            message = ChatProjectMessage(id=uuid4(), annotation_project_id=row.id,
                sender_user_id=owner.id, sender_name=owner.username, content='隔离目录测试',
                message_type='user', sequence_no=sequence, event_data={},
                created_at=business_now() - timedelta(days=1 if label == '近期' else 90))
            db.add(message); db.flush()
            if label == '历史已确认':
                db.add(ChatProjectMessageAcknowledgement(id=uuid4(), message_id=message.id, user_id=member.id))
        (expected if label in ['近期', '历史未读', '置顶', '特别关注'] else historical).add(row.id)
    db.commit()
    result = sessions(db, member, recent_only=True)
    ids = {row['project_id'] for row in result['items'] if row['kind'] == 'annotation'}
    assert ids == expected
    assert not ids.intersection(historical)
    complete = sessions(db, member)
    assert result['total'] == complete['total']
    assert result['mention_total'] == complete['mention_total']
    assert sessions(db, outsider, recent_only=True)['items'] == []


def test_history_is_paged_searchable_and_keeps_membership_boundary(environment):
    from models import AnnotationChatMember
    from chat_session_history import history_page

    db, (owner, member, outsider) = environment
    for index in range(5):
        row = project(db, owner, f'AP-HISTORY-{index}')
        row.project_name = f'历史档案 {index}'
        db.add(AnnotationChatMember(project_id=row.id, user_id=member.id, following=True, last_read_sequence=0))
    db.commit()
    first = history_page(db, member, keyword='历史档案', offset=0, limit=2)
    second = history_page(db, member, keyword='历史档案', offset=2, limit=2)
    assert first['total'] == second['total'] == 5
    assert len(first['items']) == len(second['items']) == 2
    assert not {row['key'] for row in first['items']} & {row['key'] for row in second['items']}
    assert history_page(db, member, keyword='AP-HISTORY-3')['total'] == 1
    assert history_page(db, outsider, keyword='历史档案')['total'] == 0


def test_direct_history_returns_to_recent_when_new_unread_arrives(environment):
    from business_time import business_now
    from models import ChatDirectConversation, ChatDirectMember, ChatProjectMessage
    from routers.chat_sessions import sessions

    db, (owner, member, outsider) = environment
    low, high = sorted([owner.id, member.id])
    conversation = ChatDirectConversation(id=uuid4(), user_low_id=low, user_high_id=high)
    membership = ChatDirectMember(conversation_id=conversation.id, user_id=member.id,
                                  last_read_sequence=1, pinned=False, starred=False)
    db.add_all([conversation, membership])
    message = ChatProjectMessage(id=uuid4(), direct_conversation_id=conversation.id,
        sender_user_id=owner.id, sender_name=owner.username, content='历史单聊', message_type='user',
        sequence_no=1, created_at=business_now() - timedelta(days=90), event_data={})
    db.add(message); db.commit()
    assert not [row for row in sessions(db, member, recent_only=True)['items'] if row['kind'] == 'direct']
    membership.starred = True; db.commit()
    assert len([row for row in sessions(db, member, recent_only=True)['items'] if row['kind'] == 'direct']) == 1
    membership.starred = False; membership.last_read_sequence = 0; db.commit()
    rows = [row for row in sessions(db, member, recent_only=True)['items'] if row['kind'] == 'direct']
    assert len(rows) == 1 and rows[0]['unread'] == 1
    assert not sessions(db, outsider, recent_only=True)['items']
