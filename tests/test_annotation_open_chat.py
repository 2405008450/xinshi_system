"""用真实事务验证权限、幂等、撤回、游标和附件；测试数据全部回滚。"""
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from annotation_chat_service import can_recall


def test_recall_deadline_and_ownership():
    now, sender = datetime.now(), uuid4()
    message = SimpleNamespace(message_type='user', recalled_at=None, sender_user_id=sender, created_at=now-timedelta(hours=24))
    assert can_recall(message, sender, now=now)
    assert not can_recall(message, sender, now=now+timedelta(microseconds=1))
    assert not can_recall(message, uuid4(), now=now)
    assert can_recall(message, uuid4(), admin=True, now=now+timedelta(days=30))
    message.recalled_at = now
    assert not can_recall(message, sender, admin=True)
    message.recalled_at = None
    message.message_type = 'handover'
    assert not can_recall(message, sender, admin=True)


def test_chat_clock_is_database_timezone():
    from annotation_chat_service import chat_now
    from zoneinfo import ZoneInfo
    expected = datetime.now(ZoneInfo('Asia/Hong_Kong')).replace(tzinfo=None)
    assert abs((chat_now() - expected).total_seconds()) < 2


@pytest.fixture
def environment(monkeypatch):
    if os.getenv('RUN_ANNOTATION_CHAT_DB_TESTS') != '1':
        pytest.skip('仅在局域网调试机显式开启数据库测试')
    import main  # 注册全部关联模型
    from database import engine
    from sqlalchemy.orm import Session
    from models import AppUser, Role, RolePermission, UserRole
    from annotation_models import AnnotationProject
    import annotation_chat_service as service
    import project_chat_crud
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode='create_savepoint')
    monkeypatch.setattr(service, 'publish', lambda *a, **k: None)
    monkeypatch.setattr(service, 'notify_state', lambda *a, **k: None)
    monkeypatch.setattr(project_chat_crud, '_push_notifications', lambda *a, **k: None)
    role = Role(role_name='chat-test-' + uuid4().hex[:12])
    users = [AppUser(username='chat-test-' + uuid4().hex, password_hash='disabled', full_name=f'群聊测试{i}', is_active=True) for i in range(4)]
    projects = [AnnotationProject(order_no='CHAT-' + uuid4().hex[:20], project_name='开放群测试', project_types=[]) for _ in range(2)]
    db.add_all([role, *users, *projects]); db.flush()
    db.add(RolePermission(role_id=role.id, permission_code='projects:read'))
    db.add_all(UserRole(user_id=u.id, role_id=role.id) for u in users[:3]); db.flush()
    try:
        yield db, users, projects
    finally:
        db.close(); transaction.rollback(); connection.close()


def send(db, project, user, **kwargs):
    from annotation_chat_service import send_message
    from schemas import AnnotationProjectChatMessageCreate
    return send_message(db, project.id, user, AnnotationProjectChatMessageCreate(content='测试消息', **kwargs))


def test_open_chat_idempotency_and_no_project_permission(environment):
    db, users, projects = environment
    from annotation_chat_service import require_project
    from models import AnnotationChatMember
    assert db.get(AnnotationChatMember, (projects[0].id, users[0].id)) is None
    key = uuid4()
    first = send(db, projects[0], users[0], client_message_id=key)
    retry = send(db, projects[0], users[0], client_message_id=key)
    assert retry.id == first.id
    assert db.get(AnnotationChatMember, (projects[0].id, users[0].id)).following
    with pytest.raises(HTTPException) as error:
        require_project(db, projects[0].id, users[3])
    assert error.value.status_code == 403


def test_unfollow_survives_send_invite_and_defaults(environment):
    db, users, projects = environment
    from routers.annotation_chat import follow, FollowRequest, invite, InviteRequest, group
    from models import AnnotationChatMember
    follow(projects[0].id, FollowRequest(following=False), db, users[0])
    send(db, projects[0], users[0])
    invite(projects[0].id, InviteRequest(user_ids=[users[0].id]), db, users[1])
    group(projects[0].id, db, users[0])
    member = db.get(AnnotationChatMember, (projects[0].id, users[0].id))
    assert member.explicit_unfollow and not member.following


def test_recall_redacts_reply_favorite_and_attachment(environment):
    db, users, projects = environment
    from annotation_chat_service import recall_message, serialize_many, authorize_attachment
    from models import ChatProjectAttachment, ChatProjectMessageFavorite
    attachment = ChatProjectAttachment(uploaded_by=users[0].id, annotation_project_id=projects[0].id,
        original_name='test.txt', storage_name=uuid4().hex, content_type='text/plain', file_size=5)
    db.add(attachment); db.flush()
    message = send(db, projects[0], users[0], attachment_ids=[attachment.id])
    reply = send(db, projects[0], users[1], reply_to_message_id=message.id)
    db.add(ChatProjectMessageFavorite(message_id=message.id, user_id=users[1].id)); db.commit()
    with pytest.raises(HTTPException):
        recall_message(db, projects[0].id, message.id, users[1])
    recall_message(db, projects[0].id, message.id, users[0])
    serialized, quoted = serialize_many(db, [message, reply], users[1])
    assert serialized['content'] == '' and serialized['attachments'] == [] and not serialized['is_favorited']
    assert quoted['reply']['recalled'] and '测试消息' not in quoted['reply']['content']
    with pytest.raises(HTTPException):
        authorize_attachment(db, attachment.id, users[0])
    assert recall_message(db, projects[0].id, message.id, users[0]).id == message.id
    with pytest.raises(HTTPException):
        send(db, projects[0], users[1], reply_to_message_id=message.id)


def test_cross_project_reply_and_file_are_rejected(environment):
    db, users, projects = environment
    from models import ChatProjectAttachment
    message = send(db, projects[0], users[0])
    with pytest.raises(HTTPException):
        send(db, projects[1], users[0], reply_to_message_id=message.id)
    attachment = ChatProjectAttachment(uploaded_by=users[0].id, annotation_project_id=projects[0].id,
        original_name='test.txt', storage_name=uuid4().hex, content_type='text/plain', file_size=5)
    db.add(attachment); db.flush()
    with pytest.raises(HTTPException):
        send(db, projects[1], users[0], attachment_ids=[attachment.id])
    with pytest.raises(HTTPException):
        send(db, projects[0], users[1], attachment_ids=[attachment.id])


def test_unread_cursor_and_pagination(environment):
    db, users, projects = environment
    from routers.annotation_chat import follow, FollowRequest, unread, read, ReadRequest, timeline
    from annotation_chat_service import recall_message
    follow(projects[0].id, FollowRequest(following=True), db, users[1])
    messages = [send(db, projects[0], users[0]) for _ in range(3)]
    assert unread(db, users[1])['total'] == 3
    read(projects[0].id, ReadRequest(message_id=messages[1].id), db, users[1])
    read(projects[0].id, ReadRequest(message_id=messages[0].id), db, users[1])
    assert unread(db, users[1])['total'] == 1
    recall_message(db, projects[0].id, messages[2].id, users[0])
    assert unread(db, users[1])['total'] == 0
    first = timeline(projects[0].id, limit=2, db=db, user=users[1])
    send(db, projects[0], users[0])
    earlier = timeline(projects[0].id, before=first['items'][0]['sequence_no'], limit=2, db=db, user=users[1])
    assert {m['id'] for m in first['items']}.isdisjoint(m['id'] for m in earlier['items'])


def test_followed_projects_include_read_and_empty_groups(environment):
    db, users, projects = environment
    from routers.annotation_chat import follow, FollowRequest, unread
    follow(projects[0].id, FollowRequest(following=True), db, users[1])
    result = unread(db, users[1])
    assert result['items'] == []
    assert [(row['project_id'], row['unread']) for row in result['followed_items']] == [(projects[0].id, 0)]
    follow(projects[0].id, FollowRequest(following=False), db, users[1])
    assert unread(db, users[1])['followed_items'] == []
    with pytest.raises(HTTPException) as exc:
        unread(db, users[3])
    assert exc.value.status_code == 403


def test_file_routes_and_recalled_download(environment, monkeypatch, tmp_path):
    db, users, projects = environment
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.project_chat import router
    monkeypatch.setenv('CHAT_STORAGE_MODE', 'local')
    monkeypatch.setenv('CHAT_UPLOAD_DIR', str(tmp_path))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: users[0]
    client = TestClient(app)
    base = f'/project-chat/annotation/{projects[0].id}'
    result = client.post(base + '/files', files={'file': ('report.txt', b'chat report', 'text/plain')})
    assert result.status_code == 201, result.text
    file_id = result.json()['id']
    denied = client.post(base + '/files', files={'file': ('run.exe', b'MZ test', 'application/octet-stream')})
    assert denied.status_code == 415
    large = client.post(base + '/files', files={'file': ('large.txt', b'a' * (20 * 1024 * 1024 + 1), 'text/plain')})
    assert large.status_code == 413
    bad_image = client.post(base + '/files', files={'file': ('image.png', b'not an image', 'image/png')})
    assert bad_image.status_code == 415
    key = str(uuid4())
    result = client.post(base + '/messages', json={'content': '', 'attachment_ids': [file_id], 'client_message_id': key})
    assert result.status_code == 201, result.text
    message_id = result.json()['id']
    assert result.json()['sequence_no'] and result.json()['can_recall']
    retry = client.post(base + '/messages', json={'content': '', 'attachment_ids': [file_id], 'client_message_id': key})
    assert retry.json()['id'] == message_id
    assert client.get(base + f'/files/{file_id}').content == b'chat report'
    assert client.post(base + f'/messages/{message_id}/recall').status_code == 200
    assert client.get(base + f'/files/{file_id}').status_code == 404
    assert client.get('/project-chat/attachments/' + file_id).status_code == 404


def test_admin_can_remove_expired_message(environment):
    db, users, projects = environment
    from annotation_chat_service import recall_message, chat_now
    from models import Role, UserRole
    role = db.query(Role).filter(Role.role_name == 'admin').first()
    if role is None:
        role = Role(role_name='admin'); db.add(role); db.flush()
    db.add(UserRole(user_id=users[2].id, role_id=role.id)); db.flush()
    message = send(db, projects[0], users[0])
    message.created_at = chat_now() - timedelta(days=2)
    db.commit()
    with pytest.raises(HTTPException):
        recall_message(db, projects[0].id, message.id, users[0])
    removed = recall_message(db, projects[0].id, message.id, users[2])
    assert removed.recalled_by == users[2].id and '管理员' in removed.recall_label


def test_remote_attachment_never_falls_back_to_local_backup(environment, monkeypatch, tmp_path):
    db, users, projects = environment
    from fastapi import FastAPI
    from fastapi.responses import Response
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    import routers.project_chat as routes
    from models import ChatProjectAttachment
    attachment = ChatProjectAttachment(uploaded_by=users[0].id, annotation_project_id=projects[0].id,
        original_name='backup.png', storage_name=uuid4().hex + '.png', content_type='image/png', file_size=5)
    db.add(attachment); db.flush()
    (tmp_path / attachment.storage_name).write_bytes(b'local backup')
    monkeypatch.setenv('CHAT_UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(routes, 'remote_attachment_url', lambda: 'https://storage.example/api/project-chat/attachments')
    async def remote(*args, **kwargs):
        return Response(b'cloud image', media_type='image/png')
    monkeypatch.setattr(routes, 'read_remote_attachment', remote)
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: users[0]
    client = TestClient(app)
    assert client.get(f'/project-chat/attachments/{attachment.id}').content == b'cloud image'
    async def unavailable(*args, **kwargs):
        raise HTTPException(503, '远程服务不可用')
    monkeypatch.setattr(routes, 'read_remote_attachment', unavailable)
    assert client.get(f'/project-chat/attachments/{attachment.id}').status_code == 503


def test_workflow_attachment_remains_readable_but_cannot_be_rebound(environment):
    db, users, projects = environment
    from annotation_chat_service import authorize_attachment
    from models import ChatProjectAttachment
    from workflow_models import WorkflowHandoverAttachment, WorkflowHandoverRequest
    request = WorkflowHandoverRequest(requester_id=users[0].id, target_user_id=users[1].id, handover_type='transfer')
    attachment = ChatProjectAttachment(uploaded_by=users[0].id, original_name='handover.png',
        storage_name=uuid4().hex + '.png', content_type='image/png', file_size=5)
    db.add_all([request, attachment]); db.flush()
    db.add(WorkflowHandoverAttachment(request_id=request.id, attachment_id=attachment.id)); db.flush()
    assert authorize_attachment(db, attachment.id, users[1]).id == attachment.id
    with pytest.raises(HTTPException):
        send(db, projects[0], users[0], attachment_ids=[attachment.id])
