"""目录权限按类型计算，数量增长不能带来逐会话权限查询。"""
from types import SimpleNamespace
from uuid import uuid4

import discussion_chat_service as service
import technical_task_conversations as technical
from tests.test_chat_participant_access import environment


def test_room_permissions_checked_once_and_technical_rooms_stay_hidden(monkeypatch):
    actor = SimpleNamespace(is_active=True)
    calls = {'resource': 0, 'technical': 0}
    def resource(*_):
        calls['resource'] += 1
        return True
    def development(*_):
        calls['technical'] += 1
        return False
    monkeypatch.setattr(service, 'can_view', resource)
    monkeypatch.setattr(technical, 'can_access', development)
    rooms = [dict(id=str(uuid4()), name='资源', parent_key=service.RESOURCE_ROOT) for _ in range(100)]
    rooms += [dict(id=str(uuid4()), name='技术', parent_key=technical.ROOT_ID) for _ in range(100)]
    rooms += [dict(id=str(uuid4()), name=technical.GENERAL_NAME), dict(id=str(uuid4()), name='技术任务', technical_task_id='task')]
    rooms += [dict(id=str(uuid4()), name='普通群聊', parent_key=None)]
    visible = service.visible_room_specs(None, actor, rooms)
    assert len(visible) == 101
    assert calls == {'resource': 1, 'technical': 1}
    calls.update(resource=0, technical=0)
    assert service.visible_room_specs(None, SimpleNamespace(is_active=False), rooms) == []
    assert calls == {'resource': 0, 'technical': 0}


def test_permission_result_does_not_leak_between_users_or_requests(monkeypatch):
    monkeypatch.setattr(service, 'can_view', lambda db, user: user.allowed)
    rooms = [dict(id='resource', name='资源')]
    allowed = SimpleNamespace(is_active=True, allowed=True)
    denied = SimpleNamespace(is_active=True, allowed=False)
    assert service.visible_room_specs(None, allowed, rooms) == rooms
    assert service.visible_room_specs(None, denied, rooms) == []
    allowed.allowed = False
    assert service.visible_room_specs(None, allowed, rooms) == []


def test_catalog_keeps_same_membership_and_output_with_fewer_queries(environment, monkeypatch):
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import event
    from models import AppUser
    from chat_session_category_models import ChatSessionCategory, ChatSessionCategoryFolder
    from discussion_chat_models import DiscussionMember
    db, (actor, _, outsider) = environment
    stamp = datetime(2026, 11, 4, 12, tzinfo=timezone(timedelta(hours=8)))
    for index in range(60):
        uid = uuid4()
        db.add(ChatSessionCategory(id=uid, name=f'资源群{index}', active=True, revision=1, created_at=stamp, updated_at=stamp))
        db.add(ChatSessionCategoryFolder(category_id=uid, parent_key=service.RESOURCE_ROOT))
        db.add(DiscussionMember(room_id=uid, user_id=actor.id if index < 50 else outsider.id,
            last_read_id=0, pinned=False, starred=False))
    db.commit()
    def resource(db, user):
        return db.query(AppUser.id).filter(AppUser.id == user.id).first() is not None
    monkeypatch.setattr(service, 'can_view', resource)
    optimized = service.visible_room_specs
    statements = []
    def record(_conn, _cursor, statement, *_args):
        statements.append(statement)
    event.listen(db.get_bind(), 'before_cursor_execute', record)
    try:
        monkeypatch.setattr(service, 'visible_room_specs', lambda db, user, rooms: [room for room in rooms if service.can_view_room(db, user, room)])
        before = service.catalog(db, actor)
        before_count = len(statements)
        statements.clear()
        monkeypatch.setattr(service, 'visible_room_specs', optimized)
        after = service.catalog(db, actor)
        after_count = len(statements)
    finally:
        event.remove(db.get_bind(), 'before_cursor_execute', record)
    assert before == after and len(after) == 50
    assert before_count - after_count >= 49
    print(f'chat_catalog_sql: {before_count} -> {after_count}')
