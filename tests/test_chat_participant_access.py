"""参与人访问矩阵和默认名单回归：只使用内存 SQLite，禁止连接业务数据库。"""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import CompileError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def environment(monkeypatch):
    import main  # noqa: F401 只注册模型，不执行服务启动钩子。
    from models import Base, AppUser
    import annotation_chat_service as annotation
    import chat_session_category_service as categories
    import discussion_chat_service as discussions
    from chat_default_participant_models import AnnotationChatDefaultParticipant  # noqa: F401
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    # 物理表只保留本用例需要的列和主键，避开 PostgreSQL 的序列/JSONB 默认值。
    with engine.begin() as connection:
        for table in Base.metadata.tables.values():
            columns = []
            for column in table.columns:
                try:
                    kind = column.type.compile(dialect=engine.dialect)
                except CompileError:
                    kind = 'JSON' if 'JSON' in str(column.type) else 'TEXT'
                columns.append(f'"{column.name}" {kind}')
            columns.append('PRIMARY KEY (' + ','.join(f'"{column.name}"' for column in table.primary_key.columns) + ')')
            connection.execute(text(f'CREATE TABLE "{table.name}" (' + ','.join(columns) + ')'))
    db = Session(engine, expire_on_commit=False)
    users = [AppUser(id=uuid4(), username=name, full_name=name, password_hash='disabled', is_active=True) for name in ['owner', 'member', 'outsider']]
    db.add_all(users); db.commit()
    monkeypatch.setattr(annotation, 'can_view', lambda db, user: bool(user and user.is_active))
    monkeypatch.setattr(annotation, 'eligible_users', lambda db, ids=None: db.query(AppUser).filter(AppUser.is_active.is_(True), AppUser.id.in_(ids) if ids is not None else True).all())
    monkeypatch.setattr(annotation, 'publish', lambda *a, **kw: None)
    monkeypatch.setattr(annotation, 'notify_state', lambda *a, **kw: None)
    monkeypatch.setattr(categories, 'can_manage_folders', lambda db, user: user.username == 'owner')
    monkeypatch.setattr(categories, 'changed', lambda *a: None)
    monkeypatch.setattr(discussions, 'can_view', lambda db, user: bool(user and user.is_active))
    monkeypatch.setattr(discussions, 'publish', lambda *a: None)
    yield db, users
    db.close(); engine.dispose()


def project(db, owner, number='AP-261021-001'):
    from annotation_models import AnnotationProject
    row = AnnotationProject(id=uuid4(), order_no=number, project_name='隔离权限测试', created_by=owner.id)
    db.add(row); db.commit()
    return row


def test_defaults_shared_new_chat_only_and_nonparticipant_cannot_join_existing(environment):
    db, (owner, member, outsider) = environment
    import chat_default_participant_service as defaults
    import annotation_chat_service as service
    from routers.annotation_chat import start, group
    from models import AnnotationChatMember
    defaults.save(db, owner, [member.id, member.id])
    assert defaults.catalog(db, outsider)['user_ids'] == [member.id]
    row = project(db, owner)
    start(row.id, db, owner)
    assert {uid for uid, in db.query(AnnotationChatMember.user_id).filter_by(project_id=row.id)} == {owner.id, member.id}
    assert {user['id'] for user in group(row.id, db, owner)['members']} == {owner.id, member.id}
    with pytest.raises(HTTPException) as denied:
        start(row.id, db, outsider)
    assert denied.value.status_code == 404
    with pytest.raises(HTTPException):
        service.require_project(db, row.id, outsider)
    defaults.save(db, owner, [outsider.id])
    assert db.get(AnnotationChatMember, (row.id, outsider.id)) is None
    other = project(db, owner, 'AP-261021-002')
    start(other.id, db, owner)
    assert db.get(AnnotationChatMember, (other.id, outsider.id)) is not None
    with pytest.raises(HTTPException):
        defaults.save(db, outsider, [])


def test_unfollow_is_not_membership_removal_but_outsider_cannot_read(environment):
    db, (owner, member, outsider) = environment
    from models import AnnotationChatMember
    from routers.annotation_chat import group
    row = project(db, owner)
    db.add(AnnotationChatMember(project_id=row.id, user_id=member.id, following=False, explicit_unfollow=True, last_read_sequence=0)); db.commit()
    assert group(row.id, db, member)['members'][0]['id'] == member.id
    with pytest.raises(HTTPException):
        group(row.id, db, outsider)


def test_all_conversation_memberships_are_independent_and_admin_has_no_implicit_bypass(environment):
    db, (owner, member, outsider) = environment
    from models import AnnotationChatMember, ChatProjectMemberPref
    from discussion_chat_models import DiscussionMember
    from chat_access_service import require_member, visible_ids
    for kind, model, field in [('annotation', AnnotationChatMember, 'project_id'), ('translation', ChatProjectMemberPref, 'project_id'), ('discussion', DiscussionMember, 'room_id')]:
        cid = uuid4()
        db.add(model(**{field: cid, 'user_id': member.id})); db.commit()
        require_member(db, kind, cid, member)
        assert cid in {value for value, in visible_ids(db, kind, member)}
        for denied in [owner, outsider]:
            with pytest.raises(HTTPException) as failure:
                require_member(db, kind, cid, denied)
            assert failure.value.status_code == 404


def test_legacy_annotation_message_and_attachment_routes_do_not_bypass_membership(environment, monkeypatch):
    db, (owner, member, outsider) = environment
    from models import AnnotationChatMember, ChatProjectMessage, ChatProjectAttachment, ChatProjectMessageAttachment
    import annotation_chat_service as service
    row = project(db, owner)
    db.add(AnnotationChatMember(project_id=row.id, user_id=member.id, following=True, explicit_unfollow=False, last_read_sequence=0))
    message = ChatProjectMessage(id=uuid4(), annotation_project_id=row.id, sender_user_id=member.id, sender_name='member', content='保密消息', message_type='user', sequence_no=1)
    attachment = ChatProjectAttachment(id=uuid4(), annotation_project_id=row.id, uploaded_by=member.id, original_name='test.png', storage_name='not-read.png', content_type='image/png', file_size=1)
    db.add_all([message, attachment]); db.flush()
    db.add(ChatProjectMessageAttachment(id=uuid4(), message_id=message.id, attachment_id=attachment.id)); db.commit()
    assert service.authorize_attachment(db, attachment.id, member).id == attachment.id
    with pytest.raises(HTTPException):
        service.authorize_attachment(db, attachment.id, outsider)
    from routers import project_chat
    from routers.auth import get_current_user
    from database import get_db
    import permission_service
    monkeypatch.setattr(permission_service, 'user_has_permission', lambda *a: True)
    app = FastAPI(); app.include_router(project_chat.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: outsider
    client = TestClient(app)
    for path in [f'/project-chat/annotation/{row.id}/messages', f'/project-chat/annotation/{row.id}/timeline', f'/project-chat/annotation/{row.id}/history', f'/project-chat/messages/{message.id}/favorite']:
        response = client.put(path) if path.endswith('/favorite') else client.get(path)
        assert response.status_code == 404, (path, response.text)


def test_missing_defaults_schema_fails_closed_without_automatic_creation(environment):
    db, (owner, _, _) = environment
    from chat_default_participant_models import AnnotationChatDefaultParticipant
    import chat_default_participant_service as defaults
    AnnotationChatDefaultParticipant.__table__.drop(db.connection()); db.commit()
    with pytest.raises(HTTPException) as failure:
        defaults.catalog(db, owner)
    assert failure.value.status_code == 503
    from routers.annotation_chat import start
    from models import AnnotationChatMember
    row = project(db, owner)
    with pytest.raises(HTTPException) as failure:
        start(row.id, db, owner)
    assert failure.value.status_code == 503
    assert db.query(AnnotationChatMember).count() == 0


def test_mentions_topics_and_catalog_do_not_expose_nonparticipant_or_auto_join(environment, monkeypatch):
    db, (owner, member, outsider) = environment
    from models import AnnotationChatMember, ChatProjectMessage, ChatProjectMention
    from routers.chat_sessions import sessions
    import chat_mention_history as mentions
    import chat_topic_service as topics
    row = project(db, owner)
    db.add(AnnotationChatMember(project_id=row.id, user_id=member.id, following=True, explicit_unfollow=False, last_read_sequence=0))
    message = ChatProjectMessage(id=uuid4(), annotation_project_id=row.id, sender_user_id=member.id, sender_name='member', content='保密', message_type='user', sequence_no=1)
    db.add(message); db.flush()
    db.add(ChatProjectMention(id=uuid4(), message_id=message.id, mentioned_user_id=outsider.id, mentioned_user_name='outsider')); db.commit()
    monkeypatch.setattr(topics, 'user_has_permission', lambda *a: True)
    assert mentions.mention_count(db, outsider) == 0
    assert topics.visible_messages(db, outsider).count() == 0
    assert topics.visible_messages(db, member).count() == 1
    before = db.query(AnnotationChatMember).count()
    assert sessions(db, outsider)['items'] == []
    assert db.query(AnnotationChatMember).count() == before


def test_discussion_invitation_is_required_and_nonmember_cannot_read_participants(environment, monkeypatch):
    db, (owner, member, outsider) = environment
    from uuid import UUID
    from discussion_chat_models import DiscussionMember
    from routers.chat_sessions import conversation_participants, conversation_invite, ConversationInviteWrite
    import discussion_chat_service as discussions
    import routers.chat_sessions as sessions
    monkeypatch.setattr(sessions, 'broadcast_to_users', lambda *a: None)
    room_id = UUID(discussions.room_specs(db)[0]['id'])
    db.add(DiscussionMember(room_id=room_id, user_id=owner.id, last_read_id=0, pinned=False, starred=False)); db.commit()
    assert discussions.catalog(db, outsider) == []
    with pytest.raises(HTTPException):
        conversation_participants('discussion', room_id, db, outsider)
    conversation_invite('discussion', room_id, ConversationInviteWrite(user_ids=[member.id]), db, owner)
    assert len(discussions.catalog(db, member)) == 1
    assert {row['id'] for row in conversation_participants('discussion', room_id, db, member)['members']} == {owner.id, member.id}
    assert discussions.catalog(db, outsider) == []


def test_migration_is_repeatable_preserves_existing_members_and_does_not_readmit_new_accounts(environment, monkeypatch):
    db, (owner, member, outsider) = environment
    from tools.apply_chat_participants_migration import apply_migration
    from chat_default_participant_models import AnnotationChatDefaultParticipant
    from models import TranslationProject, ChatProjectEnabled, ChatProjectMemberPref, AppUser
    import project_chat_crud
    from discussion_chat_models import DiscussionMember
    AnnotationChatDefaultParticipant.__table__.drop(db.connection()); db.commit()
    translation = TranslationProject(id=uuid4(), order_no='T-TEST', project_name='隔离迁移测试', created_by=owner.id)
    db.add(translation); db.flush()
    db.add(ChatProjectEnabled(id=uuid4(), project_id=translation.id, enabled=True)); db.commit()
    monkeypatch.setattr(project_chat_crud, '_legacy_chat_participant_user_ids', lambda *a, **kw: {owner.id})
    first = apply_migration(db); db.commit()
    assert first['translation_members_added'] == 1
    assert first['discussion_members_added'] == 18
    assert db.get(ChatProjectMemberPref, (translation.id, outsider.id)) is None
    db.add(AppUser(id=uuid4(), username='new-account', password_hash='disabled', is_active=True)); db.commit()
    second = apply_migration(db); db.commit()
    assert second == {'translation_members_added': 0, 'discussion_members_added': 0}
    assert db.query(DiscussionMember).count() == 18


@pytest.mark.parametrize('kind', ['annotation', 'translation'])
def test_explicit_mention_invites_nonmember_atomically_and_retains_unread(kind, environment):
    db, (owner, member, outsider) = environment
    from chat_access_service import MEMBERS, invite_mentioned_users, require_member
    from models import TranslationProject
    row = project(db, owner) if kind == 'annotation' else TranslationProject(id=uuid4(), order_no='T-MENTION', project_name='隔离测试', created_by=owner.id)
    if kind == 'translation': db.add(row); db.flush()
    model, column = MEMBERS[kind]
    db.add(model(**{column.key: row.id, 'user_id': owner.id})); db.commit()
    invite_mentioned_users(db, kind, row.id, owner, [member], baseline=7)
    assert db.get(model, (row.id, member.id)).last_read_sequence == 7
    require_member(db, kind, row.id, member)
    db.rollback()
    assert db.get(model, (row.id, member.id)) is None
    outsider.is_active = False; db.commit()
    with pytest.raises(ValueError): invite_mentioned_users(db, kind, row.id, owner, [member, outsider], baseline=7)
    assert db.get(model, (row.id, member.id)) is None


@pytest.mark.parametrize('kind', ['annotation', 'translation', 'discussion'])
def test_remove_and_leave_revoke_access_and_cannot_remove_self(kind, environment, monkeypatch):
    db, (owner, member, outsider) = environment
    import routers.chat_sessions as routes
    from chat_access_service import MEMBERS, require_member
    from models import TranslationProject
    from uuid import UUID
    import discussion_chat_service as discussions
    monkeypatch.setattr(routes, 'broadcast_to_users', lambda *a: None)
    if kind == 'annotation': cid = project(db, owner).id
    elif kind == 'translation':
        row = TranslationProject(id=uuid4(), order_no='T-REMOVE', project_name='隔离测试', created_by=owner.id)
        db.add(row); db.flush(); cid = row.id
    else: cid = UUID(discussions.room_specs(db)[0]['id'])
    model, column = MEMBERS[kind]
    for actor in [owner, member]: db.add(model(**{column.key: cid, 'user_id': actor.id}))
    db.commit()
    with pytest.raises(HTTPException): routes.conversation_remove_participants(kind, cid, routes.ConversationInviteWrite(user_ids=[owner.id]), db, owner)
    with pytest.raises(HTTPException): routes.conversation_remove_participants(kind, cid, routes.ConversationInviteWrite(user_ids=[member.id]), db, outsider)
    assert routes.conversation_remove_participants(kind, cid, routes.ConversationInviteWrite(user_ids=[member.id]), db, owner)['removed_count'] == 1
    with pytest.raises(HTTPException): require_member(db, kind, cid, member)
    assert routes.conversation_leave(kind, cid, db, owner)['left']
    with pytest.raises(HTTPException): require_member(db, kind, cid, owner)
    with pytest.raises(HTTPException): routes.conversation_leave(kind, cid, db, owner)


def test_message_mention_itself_joins_target_and_is_unread(environment, monkeypatch):
    db, (owner, member, outsider) = environment
    from models import AnnotationChatMember, ChatProjectMessage, ChatProjectMention
    import project_chat_crud as crud
    from routers.chat_sessions import summaries
    row = project(db, owner)
    db.add(AnnotationChatMember(project_id=row.id, user_id=owner.id, last_read_sequence=0)); db.commit()
    message = ChatProjectMessage(id=uuid4(), annotation_project_id=row.id, sender_user_id=owner.id, sender_name='owner', content='@member 测试', message_type='user', sequence_no=8)
    db.add(message); db.flush()
    # 内存表不带生产 PG 的 UUID 默认值。
    monkeypatch.setattr(crud, 'ChatProjectMention', lambda **kw: ChatProjectMention(id=uuid4(), **kw))
    users = crud._create_chat_mentions(db, message, owner, mentioned_user_ids=[member.id])
    db.flush()
    assert [target.id for target in users] == [member.id]
    membership = db.get(AnnotationChatMember, (row.id, member.id))
    assert membership.last_read_sequence == 7
    stats = summaries(db, ChatProjectMessage.annotation_project_id, [row.id], {row.id: membership.last_read_sequence}, member.id)
    assert stats[row.id]['mention_unread'] == 1
    assert db.get(AnnotationChatMember, (row.id, outsider.id)) is None
