"""独立本机 PostgreSQL 验证；禁止连接业务数据库。"""
import os
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import Session


@pytest.fixture
def environment(monkeypatch):
    url = os.getenv('CHAT_TEST_DATABASE_URL')
    if not url:
        pytest.skip('通过 tools/run_chat_phase_one_tests.py 创建隔离实例')
    parsed = make_url(url)
    assert parsed.host == '127.0.0.1' and parsed.username == 'chat_test' and parsed.database == 'postgres'
    monkeypatch.setenv('DATABASE_URL', url)
    import main
    from models import Base, AppUser, Role, RolePermission, UserRole
    import direct_chat_service as direct
    import annotation_chat_service as annotation
    import project_chat_crud
    monkeypatch.setattr(direct, 'broadcast_to_users', lambda *a, **k: None)
    monkeypatch.setattr(annotation, 'publish', lambda *a, **k: None)
    monkeypatch.setattr(annotation, 'notify_state', lambda *a, **k: None)
    monkeypatch.setattr(project_chat_crud, '_push_notifications', lambda *a, **k: None)
    schema = 'chat_' + uuid4().hex
    bootstrap = create_engine(url)
    with bootstrap.begin() as conn:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public'))
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={'options': f'-c search_path={schema},public -c timezone=Asia/Hong_Kong'})
    with engine.begin() as conn:
        conn.execute(text('CREATE SEQUENCE chat_message_sequence'))
    Base.metadata.create_all(engine, checkfirst=False)
    migration = (Path(__file__).resolve().parents[1] / 'data/migrations/20261010_chat_phase_one.sql').read_text(encoding='utf-8')
    with engine.begin() as conn:
        conn.execute(text(migration)); conn.execute(text(migration))
    db = Session(engine, expire_on_commit=False)
    users = [AppUser(username='chat-' + uuid4().hex, password_hash='disabled', full_name=f'聊天测试{i}', is_active=True) for i in range(4)]
    role = Role(role_name='chat-test-' + uuid4().hex[:10])
    db.add_all([*users, role]); db.flush()
    db.add(RolePermission(role_id=role.id, permission_code='projects:read'))
    db.add_all(UserRole(user_id=u.id, role_id=role.id) for u in users[:3]); db.commit()
    try:
        yield db, users, engine
    finally:
        main.app.dependency_overrides.clear()
        db.close(); engine.dispose()
        with bootstrap.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        bootstrap.dispose()


def send(db, cid, user, **kwargs):
    from direct_chat_service import send_message
    from schemas import AnnotationProjectChatMessageCreate
    return send_message(db, cid, user, AnnotationProjectChatMessageCreate(content='你好 https://example.org', **kwargs))


def test_pair_idempotency_concurrency_and_member_access(environment):
    db, users, engine = environment
    import direct_chat_service as service
    from models import ChatDirectConversation, ChatDirectMember
    def opened(pair):
        with Session(engine) as session:
            return service.open_conversation(session, session.get(type(users[0]), pair[0]), pair[1])['id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(opened, [(users[0].id, users[1].id), (users[1].id, users[0].id)]))
    assert ids[0] == ids[1]
    assert db.query(ChatDirectConversation).count() == 1 and db.query(ChatDirectMember).count() == 2
    with pytest.raises(HTTPException):
        service.require_project(db, ids[0], users[2])
    with pytest.raises(HTTPException):
        service.open_conversation(db, users[0], users[0].id)
    users[2].is_active = False; db.commit()
    with pytest.raises(HTTPException):
        service.open_conversation(db, users[0], users[2].id)
    # 无项目权限的启用用户可以私聊。
    assert service.open_conversation(db, users[0], users[3].id)['id']


def test_lifecycle_reply_attachment_read_history_and_preferences(environment):
    db, users, engine = environment
    import direct_chat_service as service
    from models import ChatProjectAttachment, ChatProjectMessageFavorite
    from routers.direct_chat import timeline, read, ReadRequest, history
    from routers.chat_sessions import sessions, preferences, PreferenceRequest
    cid = service.open_conversation(db, users[0], users[1].id)['id']
    other = service.open_conversation(db, users[0], users[2].id)['id']
    attachment = ChatProjectAttachment(uploaded_by=users[0].id, direct_conversation_id=cid,
        original_name='测试.txt', storage_name=uuid4().hex, content_type='text/plain', file_size=5)
    db.add(attachment); db.commit()
    first = send(db, cid, users[0], client_message_id=uuid4(), attachment_ids=[attachment.id])
    retry = send(db, cid, users[0], client_message_id=first.client_message_id, attachment_ids=[attachment.id])
    assert first.id == retry.id
    reply = send(db, cid, users[1], reply_to_message_id=first.id)
    for action in (lambda: send(db, other, users[0], reply_to_message_id=first.id),
                   lambda: send(db, other, users[0], attachment_ids=[attachment.id]),
                   lambda: service.authorize_attachment(db, attachment.id, users[2]),
                   lambda: send(db, cid, users[0], mentioned_user_ids=[users[1].id])):
        with pytest.raises(HTTPException): action()
    rows = timeline(cid, limit=1, db=db, user=users[1])['items']
    assert rows[0]['id'] == reply.id and rows[0]['created_at'].utcoffset() == timedelta(hours=8)
    assert timeline(cid, before=reply.sequence_no, limit=1, db=db, user=users[1])['items'][0]['id'] == first.id
    assert history(cid, kind='all', limit=30, db=db, user=users[1])['items'][0]['message_id'] == reply.id
    assert history(cid, kind='file', limit=30, db=db, user=users[1])['items'][0]['attachment']['id'] == attachment.id
    assert sessions(db, users[1])['total'] == 1
    read(cid, ReadRequest(message_id=reply.id), db, users[1]); read(cid, ReadRequest(message_id=first.id), db, users[1])
    assert sessions(db, users[1])['total'] == 0
    preferences('direct', cid, PreferenceRequest(pinned=True, starred=True), db, users[1])
    row = sessions(db, users[1])['items'][0]
    assert row['pinned'] and row['starred'] and not sessions(db, users[0])['items'][0]['pinned']
    db.add(ChatProjectMessageFavorite(message_id=first.id, user_id=users[1].id)); db.commit()
    with pytest.raises(HTTPException): service.recall_message(db, cid, first.id, users[1])
    service.recall_message(db, cid, first.id, users[0])
    data = service.serialize_many(db, [first, reply], users[1])
    assert not data[0]['content'] and not data[0]['attachments'] and not data[0]['is_favorited']
    assert data[1]['reply']['recalled']
    with pytest.raises(HTTPException): service.authorize_attachment(db, attachment.id, users[0])
    assert service.recall_message(db, cid, first.id, users[0]).id == first.id


def test_annotation_mentions_translation_and_api_security(environment, monkeypatch, tmp_path):
    db, users, engine = environment
    from annotation_models import AnnotationProject
    from models import TranslationProject, AnnotationChatMember, ChatProjectMessage, ChatProjectMention
    from schemas import AnnotationProjectChatMessageCreate
    from routers.chat_sessions import sessions, preferences, PreferenceRequest
    import annotation_chat_service as annotation
    import direct_chat_service as direct
    from database import get_db
    from routers.auth import get_current_user
    import main
    from routers import project_chat
    monkeypatch.setattr(project_chat, 'get_chat_upload_dir', lambda: tmp_path)
    monkeypatch.setenv('CHAT_ATTACHMENT_REMOTE_URL', '')
    project = AnnotationProject(order_no='CHAT-' + uuid4().hex[:20], project_name='提醒测试', project_types=[], created_by=users[0].id)
    translation = TranslationProject(order_no='TP-' + uuid4().hex[:20], project_name='笔译测试', created_by=users[0].id)
    db.add_all([project, translation]); db.commit()
    annotation.add_member(db, project.id, users[1].id, baseline=0); db.commit()
    message = annotation.send_message(db, project.id, users[0], AnnotationProjectChatMessageCreate(content='@聊天测试1 请确认', mentioned_user_ids=[users[1].id]))
    rows = sessions(db, users[1])['items']
    group = next(r for r in rows if r['kind'] == 'annotation')
    assert group['mention_unread'] == 1 and group['mention_message_ids'] == [message.id]
    preferences('annotation', project.id, PreferenceRequest(mark_read=True), db, users[1])
    assert next(r for r in sessions(db, users[1])['items'] if r['kind'] == 'annotation')['mention_unread'] == 0
    preferences('translation', translation.id, PreferenceRequest(starred=True), db, users[1])
    assert next(r for r in sessions(db, users[1])['items'] if r['kind'] == 'translation')['starred']
    cid = direct.open_conversation(db, users[0], users[1].id)['id']
    dm = send(db, cid, users[0])
    main.app.dependency_overrides[get_db] = lambda: db
    actor = [users[1]]
    main.app.dependency_overrides[get_current_user] = lambda: actor[0]
    client = TestClient(main.app)
    assert client.get(f'/chat/direct/{cid}/timeline').status_code == 200
    assert client.put(f'/project-chat/messages/{dm.id}/favorite').status_code == 200
    assert client.put(f'/project-chat/messages/{dm.id}/acknowledgement').status_code == 200
    actor[0] = users[2]
    assert client.get(f'/chat/direct/{cid}/timeline').status_code == 404
    assert client.put(f'/project-chat/messages/{dm.id}/favorite').status_code == 404
    assert client.put(f'/project-chat/messages/{dm.id}/acknowledgement').status_code == 404
    actor[0] = users[0]
    uploaded = client.post(f'/chat/direct/{cid}/files', files={'file': ('测试.txt', b'test', 'text/plain')})
    assert uploaded.status_code == 201, uploaded.text
    fid = uploaded.json()['id']
    send(db, cid, users[0], attachment_ids=[fid])
    actor[0] = users[1]
    assert client.get(f'/chat/direct/{cid}/files/{fid}').content == b'test'
    actor[0] = users[2]
    assert client.get(f'/project-chat/attachments/{fid}').status_code == 404


def remove_phase_one_columns(db, engine):
    from chat_schema import _ready
    db.close()
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE chat_project_message DROP COLUMN direct_conversation_id CASCADE'))
        conn.execute(text('ALTER TABLE chat_project_attachment DROP COLUMN direct_conversation_id CASCADE'))
        conn.execute(text('ALTER TABLE annotation_chat_member DROP COLUMN pinned, DROP COLUMN starred'))
        conn.execute(text('DROP TABLE chat_mention_notification_target'))
    _ready.cache_clear()


def test_legacy_schema_remains_usable_before_migration(environment):
    db, users, engine = environment
    from annotation_models import AnnotationProject
    from models import ChatProjectAttachment
    from schemas import AnnotationProjectChatMessageCreate
    from routers.chat_sessions import sessions
    import annotation_chat_service as annotation
    remove_phase_one_columns(db, engine)
    project = AnnotationProject(order_no='OLD-' + uuid4().hex[:20], project_name='旧群兼容', project_types=[])
    db.add(project); db.commit()
    message = annotation.send_message(db, project.id, users[0], AnnotationProjectChatMessageCreate(content='旧结构仍可发消息'))
    assert annotation.serialize_many(db, [message], users[1])[0]['content'] == '旧结构仍可发消息'
    attachment = ChatProjectAttachment(uploaded_by=users[0].id, annotation_project_id=project.id,
        original_name='旧文件.txt', storage_name=uuid4().hex, content_type='text/plain', file_size=4)
    db.add(attachment); db.commit()
    assert annotation.authorize_attachment(db, attachment.id, users[0]).id == attachment.id
    assert not sessions(db, users[0])['phase_one_enabled']


@pytest.mark.parametrize('migrated', [False, True])
@pytest.mark.parametrize('following', [False, True])
def test_session_mention_preview_and_read_state_in_both_schemas(environment, migrated, following):
    db, users, engine = environment
    from annotation_models import AnnotationProject
    from models import AnnotationChatMember
    from schemas import AnnotationProjectChatMessageCreate
    from routers.chat_sessions import sessions, preferences, PreferenceRequest
    import annotation_chat_service as annotation
    if not migrated:
        remove_phase_one_columns(db, engine)
    project = AnnotationProject(order_no='PREVIEW-' + uuid4().hex[:16], project_name='列表提及预览', project_types=[])
    db.add(project); db.commit()
    member = annotation.add_member(db, project.id, users[1].id, following=following, baseline=0)
    member.explicit_unfollow = not following; db.commit()
    message = annotation.send_message(db, project.id, users[0], AnnotationProjectChatMessageCreate(
        content='@聊天测试1 请确认列表提醒', mentioned_user_ids=[users[1].id]))
    data = sessions(db, users[1])
    row = next(r for r in data['items'] if r['project_id'] == project.id)
    assert data['phase_one_enabled'] is migrated and data['mention_total'] == 1
    assert row['unread'] == row['mention_unread'] == 1 and row['mention_message_ids'] == [message.id]
    assert row['last_message']['preview'] == message.content and row['last_message']['mentions_me']
    assert row['last_message']['created_at'].utcoffset() == timedelta(hours=8)
    assert row['following'] is following
    preferences('annotation', project.id, PreferenceRequest(mark_read=True), db, users[1])
    data = sessions(db, users[1])
    assert data['mention_total'] == data['total'] == 0
    assert db.get(AnnotationChatMember, (project.id, users[1].id)).following is following
    if following:
        row = next(r for r in data['items'] if r['project_id'] == project.id)
        assert row['mention_unread'] == 0 and row['last_message']['mentions_me']
        annotation.recall_message(db, project.id, message.id, users[0])
        row = next(r for r in sessions(db, users[1])['items'] if r['project_id'] == project.id)
        assert not row['last_message']['mentions_me'] and '撤回' in row['last_message']['preview']
    else:
        assert not any(r['project_id'] == project.id for r in data['items'])


def test_message_retry_concurrency_and_recall_deadline(environment):
    db, users, engine = environment
    import direct_chat_service as service
    from models import AppUser
    from chat_time import now
    cid = service.open_conversation(db, users[0], users[1].id)['id']
    key = uuid4()
    def worker(_):
        with Session(engine) as session:
            return send(session, cid, session.get(AppUser, users[0].id), client_message_id=key).id
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(worker, range(2)))
    assert ids[0] == ids[1] and service.message_query(db, cid).count() == 1
    message = service.message_query(db, cid).first()
    message.created_at = now().replace(tzinfo=None) - timedelta(hours=25); db.commit()
    with pytest.raises(HTTPException): service.recall_message(db, cid, message.id, users[0])


def test_exact_notification_target_and_foreign_read_are_rejected(environment):
    db, users, engine = environment
    import annotation_chat_service as annotation
    from annotation_models import AnnotationProject
    from models import AppNotification
    from schemas import AnnotationProjectChatMessageCreate
    from routers.chat_sessions import mention_target, preferences, PreferenceRequest
    project = AnnotationProject(order_no='MENTION-' + uuid4().hex[:18], project_name='精确通知', project_types=[])
    db.add(project); db.commit()
    payload = AnnotationProjectChatMessageCreate(content='@聊天测试1 第一条', mentioned_user_ids=[users[1].id])
    first = annotation.send_message(db, project.id, users[0], payload)
    second = annotation.send_message(db, project.id, users[0], payload)
    notifications = db.query(AppNotification).filter_by(recipient_user_id=users[1].id).order_by(AppNotification.created_at).all()
    assert [mention_target(n.id, db, users[1])['message_id'] for n in notifications] == [first.id, second.id]
    with pytest.raises(HTTPException): mention_target(notifications[0].id, db, users[2])
    import direct_chat_service as direct
    cid = direct.open_conversation(db, users[0], users[1].id)['id']
    with pytest.raises(HTTPException): preferences('direct', cid, PreferenceRequest(read_message_id=first.id), db, users[1])


def test_unfollowed_mention_still_appears_without_changing_follow_preference(environment):
    db, users, engine = environment
    from annotation_models import AnnotationProject
    from schemas import AnnotationProjectChatMessageCreate
    from models import AnnotationChatMember
    from routers.chat_sessions import sessions
    from routers.annotation_chat import read, ReadRequest
    import annotation_chat_service as annotation
    project = AnnotationProject(order_no='UNFOLLOW-' + uuid4().hex[:16], project_name='未关注提醒', project_types=[])
    db.add(project); db.commit()
    member = annotation.add_member(db, project.id, users[1].id, following=False, baseline=0)
    member.explicit_unfollow = True; db.commit()
    message = annotation.send_message(db, project.id, users[0], AnnotationProjectChatMessageCreate(content='@聊天测试1 请查看', mentioned_user_ids=[users[1].id]))
    row = next(r for r in sessions(db, users[1])['items'] if r['project_id'] == project.id)
    assert row['mention_unread'] == 1
    assert not db.get(AnnotationChatMember, (project.id, users[1].id)).following
    read(project.id, ReadRequest(message_id=message.id), db, users[1])
    assert not any(r['project_id'] == project.id for r in sessions(db, users[1])['items'])
