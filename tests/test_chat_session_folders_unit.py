"""目录层级及管理权限回归；仅使用内存 SQLite，绝不连接业务库。"""
from types import SimpleNamespace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import workflow_models  # 注册 TranslationProject 的既有工作流关联。
import recruitment_models
import interpretation_models
import annotation_ops_models

import chat_session_category_service as service
from chat_session_category_models import ChatSessionCategory as Category, ChatSessionCategoryFolder as Folder
from routers import chat_session_categories as api


@pytest.fixture
def local_db(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE app_user (id CHAR(32) PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE chat_session_category_link (id CHAR(32) PRIMARY KEY)'))
    Category.__table__.create(engine)
    Folder.__table__.create(engine)
    from discussion_chat_models import DiscussionMember, DiscussionMessage
    DiscussionMember.__table__.create(engine)
    DiscussionMessage.__table__.create(engine)
    monkeypatch.setattr(service, 'changed', lambda db: None)
    monkeypatch.setattr(service, 'user_has_permission', lambda db, uid, permission: False)
    with Session(engine) as db:
        yield db
    engine.dispose()


def actor(username='Jimmy', active=True):
    return SimpleNamespace(id=uuid4(), username=username, full_name='', is_active=active)


def test_resource_discussions_cannot_be_disabled_but_can_be_renamed(local_db):
    resource = next(row['id'] for row in service.BUILTIN_FOLDERS if row['ruleKey'] == 'resource')
    user = actor()
    discussion = api.create(api.CategoryCreate(name='不可删除的讨论', parent_key=resource), local_db, user)
    with pytest.raises(HTTPException) as denied:
        api.update(UUID(discussion['id']), api.CategoryUpdate(revision=1, active=False), local_db, user)
    assert denied.value.status_code == 422
    saved = api.update(UUID(discussion['id']), api.CategoryUpdate(revision=1, name='改名后的讨论'), local_db, user)
    assert saved['name'] == '改名后的讨论'
    assert saved['active'] is True


def test_builtin_resource_discussion_name_override_keeps_identity(local_db, monkeypatch):
    import discussion_chat_service as discussions
    from routers.discussion_chat import DiscussionNameWrite, rename
    monkeypatch.setattr(discussions, 'can_view', lambda db, user: True)
    user = actor()
    builtin = next(row for row in service.BUILTIN_FOLDERS if row['parentKey'] == discussions.RESOURCE_ROOT)
    room_id = UUID(builtin['id'])
    from discussion_chat_models import DiscussionMember
    local_db.add(DiscussionMember(room_id=room_id, user_id=user.id, last_read_id=0, pinned=False, starred=False)); local_db.flush()
    saved = rename(room_id, DiscussionNameWrite(name='固定讨论改名'), local_db, user)
    assert saved['id'] == builtin['id']
    assert next(row for row in discussions.room_specs(local_db) if row['id'] == builtin['id'])['name'] == '固定讨论改名'
    with pytest.raises(HTTPException) as denied:
        api.update(room_id, api.CategoryUpdate(revision=saved['revision'], active=False), local_db, user)
    assert denied.value.status_code == 422


def test_only_super_admin_or_real_jimmy_account_can_manage(local_db, monkeypatch):
    assert service.can_manage_folders(local_db, actor())
    assert service.can_manage_folders(local_db, actor('jimmy'))
    imposter = actor('ordinary'); imposter.full_name = 'Jimmy'
    assert not service.can_manage_folders(local_db, imposter)
    assert not service.can_manage_folders(local_db, actor(active=False))
    with pytest.raises(HTTPException) as denied:
        service.require_manager(local_db, imposter)
    assert denied.value.status_code == 403
    monkeypatch.setattr(service, 'user_has_permission', lambda db, uid, permission: permission == '*')
    assert service.can_manage_folders(local_db, actor('super-admin'))


def test_root_child_catalog_and_third_level_rejection(local_db):
    user = actor()
    root = api.create(api.CategoryCreate(name='高校资源'), local_db, user)
    child = api.create(api.CategoryCreate(name='高校平台', parent_key=root['id']), local_db, user)
    assert child['parent_key'] == root['id']
    assert service.catalog(local_db, user)['hierarchy_ready']
    assert next(row for row in service.catalog(local_db, user)['items'] if row['id'] == child['id'])['parent_key'] == root['id']
    with pytest.raises(HTTPException) as denied:
        api.create(api.CategoryCreate(name='禁止三级', parent_key=child['id']), local_db, user)
    assert denied.value.status_code == 422
    api.update(UUID(child['id']), api.CategoryUpdate(name='高校平台改名', revision=1), local_db, user)
    assert local_db.get(Folder, UUID(child['id'])).parent_key == root['id']
    with pytest.raises(HTTPException) as conflict:
        api.update(UUID(child['id']), api.CategoryUpdate(name='旧版本', revision=1), local_db, user)
    assert conflict.value.status_code == 409


def test_builtin_parent_and_invalid_or_inactive_parent(local_db):
    user = actor()
    root = service.BUILTIN_FOLDERS[1]['id']
    row = api.create(api.CategoryCreate(name='重点项目', parent_key=root), local_db, user)
    assert row['parent_key'] == root
    for name in ('标注项目', '项目进行中'):
        with pytest.raises(HTTPException) as duplicate:
            api.create(api.CategoryCreate(name=name, parent_key=root), local_db, user)
        assert duplicate.value.status_code == 409
    with pytest.raises(HTTPException):
        service.validate_parent(local_db, uuid4())
    custom = api.create(api.CategoryCreate(name='暂时停用'), local_db, user)
    api.update(UUID(custom['id']), api.CategoryUpdate(active=False, revision=1), local_db, user)
    with pytest.raises(HTTPException):
        service.validate_parent(local_db, UUID(custom['id']))


def test_unmigrated_hierarchy_preserves_legacy_catalog_and_rejects_children(local_db):
    user = actor()
    root = api.create(api.CategoryCreate(name='原有一级分类'), local_db, user)
    Folder.__table__.drop(local_db.get_bind())
    result = service.catalog(local_db, user)
    assert result['ready'] and not result['hierarchy_ready']
    assert result['items'][0]['id'] == root['id']
    with pytest.raises(HTTPException) as blocked:
        api.create(api.CategoryCreate(name='待迁移二级', parent_key=root['id']), local_db, user)
    assert blocked.value.status_code == 503
    assert local_db.query(Category).count() == 1


def test_reading_builtin_group_catalog_does_not_create_categories(local_db):
    user = actor()
    assert local_db.query(Category).count() == 0
    service.catalog(local_db, user)
    assert local_db.query(Category).count() == 0


def test_folder_migration_is_repeatable_and_does_not_seed_categories(local_db):
    Folder.__table__.drop(local_db.get_bind())
    sql = (Path(__file__).resolve().parents[1] / 'data/migrations/20261020_chat_session_folders.sql').read_text(encoding='utf-8')
    raw = local_db.get_bind().raw_connection()
    try:
        raw.driver_connection.executescript(sql)
        raw.driver_connection.executescript(sql)
    finally:
        raw.close()
    assert service.folder_schema_ready(local_db)
    assert local_db.query(Category).count() == 0
