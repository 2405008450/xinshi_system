"""目录计算只在本次调用内复用，不跨会话、账号或异常保留权限结果。"""
from types import SimpleNamespace

import pytest
from uuid import uuid4
from test_chat_participant_access import environment

from chat_catalog_read import catalog_cached, catalog_read_scope


def test_cache_is_scoped_to_each_read_and_argument():
    calls = []

    @catalog_cached
    def read(db, actor):
        calls.append(actor)
        return len(calls)

    first, second = SimpleNamespace(info={}), SimpleNamespace(info={})
    assert read(first, 'a') != read(first, 'a')
    with catalog_read_scope(first):
        assert read(first, 'a') == read(first, 'a')
        assert read(first, 'b') != read(first, 'a')
        assert read(second, 'a') != read(first, 'a')
        with catalog_read_scope(first):
            assert read(first, 'a') == read(first, 'a')
        saved = read(first, 'a')
    assert first.info == {}
    with catalog_read_scope(first):
        assert read(first, 'a') != saved
    with pytest.raises(RuntimeError):
        with catalog_read_scope(first):
            read(first, 'a')
            raise RuntimeError('隔离异常')
    assert first.info == {}


def test_permission_changes_are_visible_on_next_catalog_read(environment):
    from models import Role, RolePermission, UserRole
    from permission_service import get_user_permission_codes

    db, (_owner, actor, outsider) = environment
    role = Role(id=uuid4(), role_name='目录隔离测试')
    grant = RolePermission(id=uuid4(), role_id=role.id, permission_code='talents:read')
    db.add_all([role, grant, UserRole(id=uuid4(), user_id=actor.id, role_id=role.id)])
    db.commit()
    with catalog_read_scope(db):
        assert 'talents:read' in get_user_permission_codes(db, actor.id)
        assert 'talents:read' not in get_user_permission_codes(db, outsider.id)
    db.delete(grant); db.commit()
    with catalog_read_scope(db):
        assert 'talents:read' not in get_user_permission_codes(db, actor.id)
