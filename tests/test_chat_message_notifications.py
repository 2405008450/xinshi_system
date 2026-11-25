"""普通聊天提醒回归：只使用内存 SQLite 或显式隔离 PostgreSQL。"""
from uuid import uuid4
import pytest
from sqlalchemy import event
from discussion_chat_service import publish as publish_discussion

from test_chat_participant_access import environment  # noqa: F401
from test_chat_mentions_all import chat_env, setup_discussion  # noqa: F401
from test_chat_phase_one import environment as pg_environment  # noqa: F401


@pytest.fixture
def notify_env(chat_env):
    from models import AppNotification
    def defaults(mapper, connection, row):
        if row.is_read is None:
            row.is_read = False
    event.listen(AppNotification, 'before_insert', defaults)
    try:
        yield chat_env
    finally:
        event.remove(AppNotification, 'before_insert', defaults)


def direct_pair(db, users):
    from models import ChatDirectConversation, ChatDirectMember
    pair = ChatDirectConversation(id=uuid4(), user_low_id=min(u.id for u in users[:2]), user_high_id=max(u.id for u in users[:2]))
    db.add(pair)
    db.add_all(ChatDirectMember(conversation_id=pair.id, user_id=u.id, last_read_sequence=0) for u in users[:2])
    db.commit()
    return pair.id


def check_direct(db, users):
    import direct_chat_service as service
    from models import AppNotification
    from schemas import AnnotationProjectChatMessageCreate as Payload
    from routers.direct_chat import read, ReadRequest
    from routers.chat_sessions import mention_target
    from crud import get_notifications
    cid = direct_pair(db, users)
    payload = Payload(content='普通私聊正文不进入通知', client_message_id=uuid4())
    first = service.send_message(db, cid, users[0], payload)
    service.send_message(db, cid, users[0], payload)
    notices = db.query(AppNotification).all()
    assert len(notices) == 1
    notice = notices[0]
    assert notice.notification_type == 'direct_chat' and notice.recipient_user_id == users[1].id
    assert '普通私聊正文' not in notice.content
    assert mention_target(notice.id, db, users[1])['message_id'] == first.id
    assert get_notifications(db, users[1].id, channel='business') == []
    assert len(get_notifications(db, users[1].id, channel='chat', notification_ids=[notice.id])) == 1
    assert get_notifications(db, users[2].id, channel='chat', notification_ids=[notice.id]) == []
    read(cid, ReadRequest(message_id=first.id), db, users[1])
    assert notice.is_read
    second = service.send_message(db, cid, users[0], Payload(content='@接收人', mentioned_user_ids=[users[1].id], client_message_id=uuid4()))
    assert db.query(AppNotification).count() == 2
    service.recall_message(db, cid, second.id, users[0])
    assert all(n.is_read for n in db.query(AppNotification))
    assert mention_target(db.query(AppNotification).filter_by(notification_type='direct_chat_mention').one().id, db, users[1])['message_id'] is None


def test_notify_direct_read_recall_dedup_and_visibility(notify_env):
    db, users = notify_env
    check_direct(db, users)


def test_notify_postgres_direct(pg_environment):
    db, users, _ = pg_environment
    check_direct(db, users)


def test_group_recipient_permission_is_batched_and_matches_existing_rules(notify_env):
    from annotation_chat_service import annotation_department_member, project_chat_eligible_ids
    from department_models import Department, DepartmentMember
    from models import AppUser, Role, RolePermission, UserRole
    from permission_service import user_has_permission

    db, users = notify_env
    accounts = {
        name: AppUser(id=uuid4(), username=name, password_hash='disabled', is_active=name != 'batch-inactive')
        for name in ('batch-admin', 'batch-legacy', 'batch-department', 'batch-inactive', 'batch-wildcard', 'batch-denied')
    }
    accounts['batch-legacy'].department = '标注项目部'
    accounts['batch-inactive'].department = '标注项目部'
    department = Department(id=uuid4(), name='标注项目部')
    admin = Role(id=uuid4(), role_name='admin')
    wildcard = Role(id=uuid4(), role_name='历史通配符角色')
    db.add_all([*accounts.values(), admin, wildcard, department])
    db.add_all([
        DepartmentMember(department_id=department.id, user_id=accounts['batch-department'].id),
        RolePermission(id=uuid4(), role_id=wildcard.id, permission_code='*'),
        UserRole(id=uuid4(), role_id=admin.id, user_id=accounts['batch-admin'].id),
        UserRole(id=uuid4(), role_id=wildcard.id, user_id=accounts['batch-wildcard'].id),
    ])
    db.commit()
    people = [*users, *accounts.values()]
    ids = {person.id for person in people}
    translation = {person.id for person in people if person.is_active and user_has_permission(db, person.id, 'projects:read')}
    annotation = translation | {person.id for person in people if annotation_department_member(db, person)}
    assert translation == {*(person.id for person in users), accounts['batch-admin'].id}
    assert annotation - translation == {accounts['batch-legacy'].id, accounts['batch-department'].id}

    statements = []

    def capture(_conn, _cursor, statement, *_args):
        statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        assert project_chat_eligible_ids(db, ids) == translation
        assert project_chat_eligible_ids(db, ids, allow_annotation_department=True) == annotation
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert len(statements) == 2


def test_notify_annotation_members_permissions_and_mentions(notify_env, monkeypatch):
    db, users = notify_env
    from models import AppUser, AppNotification, AnnotationChatMember
    from annotation_models import AnnotationProject
    from schemas import AnnotationProjectChatMessageCreate as Payload
    import annotation_chat_service as service
    from routers.annotation_chat import read, ReadRequest
    inactive = AppUser(id=uuid4(), username='disabled', password_hash='disabled', is_active=False)
    extra = AppUser(id=uuid4(), username='extra', password_hash='disabled', is_active=True, department='标注项目部')
    denied = AppUser(id=uuid4(), username='denied', password_hash='disabled', is_active=True)
    db.add_all([inactive, extra, denied])
    project = AnnotationProject(id=uuid4(), order_no='AP-NOTIFY', project_name='提醒测试', created_by=users[0].id)
    db.add(project)
    db.add_all(AnnotationChatMember(project_id=project.id, user_id=u.id, following=True, last_read_sequence=0) for u in [*users[:2], inactive, extra, denied])
    db.commit()
    monkeypatch.setattr(service, 'can_view', lambda db, u: bool(u and u.is_active and u.id != denied.id))
    payload = Payload(content='群聊', mentioned_user_ids=[users[1].id], client_message_id=uuid4())
    first = service.send_message(db, project.id, users[0], payload)
    service.send_message(db, project.id, users[0], payload)
    notices = db.query(AppNotification).all()
    assert {(n.recipient_user_id, n.notification_type) for n in notices} == {(users[1].id, 'annotation_project_chat_mention'), (extra.id, 'annotation_project_chat')}
    second = service.send_message(db, project.id, users[0], Payload(content='下一条', client_message_id=uuid4()))
    read(project.id, ReadRequest(message_id=first.id), db, extra)
    assert db.query(AppNotification).filter_by(recipient_user_id=extra.id, is_read=False).count() == 1
    service.recall_message(db, project.id, second.id, users[0])
    assert db.query(AppNotification).filter_by(recipient_user_id=extra.id, is_read=False).count() == 0


def test_notify_discussion_members_read_and_recall(notify_env, monkeypatch):
    db, users = notify_env
    from models import AppNotification
    from routers.discussion_chat import MessageCreate, PreferenceWrite, recall
    import discussion_chat_service as service
    room = setup_discussion(db, users)
    broadcasts = []
    monkeypatch.setattr(service, 'publish', publish_discussion)
    monkeypatch.setattr(service, 'broadcast_to_users', lambda ids, event: broadcasts.append((set(ids), event)))
    payload = MessageCreate(content='普通讨论', client_message_id=uuid4())
    first = service.send(db, users[0], room, payload)
    service.send(db, users[0], room, payload)
    assert broadcasts == [({users[0].id, users[1].id}, {
        'type': 'chat_sessions_changed', 'projectType': 'discussion',
        'projectId': str(room), 'membersChanged': False, 'kind': 'message',
    })]
    notice = db.query(AppNotification).one()
    assert notice.notification_type == 'discussion_chat' and notice.recipient_user_id == users[1].id
    service.preferences(db, users[1], room, PreferenceWrite(read_message_id=int(first['id'])))
    assert notice.is_read
    second = service.send(db, users[0], room, MessageCreate(content='新消息', client_message_id=uuid4()))
    recall(room, int(second['id']), db, users[0])
    assert db.query(AppNotification).filter_by(is_read=False).count() == 0


def test_notify_translation_all_members_not_only_default(notify_env, monkeypatch):
    db, users = notify_env
    from models import AppNotification, TranslationProject, ChatProjectMemberPref, ChatProjectEnabled
    from project_chat_crud import create_project_chat_message
    from chat_message_notifications import settle_notifications
    import permission_service
    monkeypatch.setattr(permission_service, 'user_has_permission', lambda db, uid, code: True)
    row = TranslationProject(id=uuid4(), order_no='TP-NOTIFY', project_name='项目群提醒', created_by=users[0].id)
    db.add(row); db.flush()
    db.add(ChatProjectEnabled(id=uuid4(), project_id=row.id, enabled=True, enabled_by=users[0].id))
    db.add_all(ChatProjectMemberPref(project_id=row.id, user_id=u.id, last_read_sequence=0) for u in users[:2])
    db.commit()
    message = create_project_chat_message(db, row.id, users[0], content='新消息')
    notice = db.query(AppNotification).one()
    assert notice.notification_type == 'project_chat' and notice.recipient_user_id == users[1].id
    settle_notifications(db, 'translation', row.id, user_id=users[1].id, sequence=message.sequence_no)
    assert notice.is_read
