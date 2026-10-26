"""团队归类共享，授权和目录范围始终由原会话决定。"""
from fastapi import HTTPException
import json
from pathlib import Path
from uuid import UUID
from sqlalchemy import inspect, or_
from sqlalchemy.exc import IntegrityError
from business_time import business_iso
from models import AppUser, TranslationProject
from permission_service import user_has_permission
from notification_ws import broadcast_to_users
from chat_session_category_models import ChatSessionCategory as Category, ChatSessionCategoryLink as Link, ChatSessionCategoryFolder as Folder

BUILTIN_FOLDERS = json.loads((Path(__file__).parent / 'data/chat_session_folders.json').read_text(encoding='utf-8'))
BUILTIN_INDEX = {row['id']: row for row in BUILTIN_FOLDERS}


def folder_schema_ready(db):
    return inspect(db.connection()).has_table(Folder.__tablename__)


def can_manage_folders(db, user):
    # 使用真实账号名，不能用可修改的显示名授予 Jimmy 的专属权限。
    return bool(user.is_active and ((user.username or '').casefold() == 'jimmy'
                or user_has_permission(db, user.id, '*')))

SYSTEM_NAMES = frozenset(('消息', '置顶', '未读', '@我', '单聊', '特别关注', '项目群', '标注项目群', '笔译项目群', '我创建的'))
TARGETS = {'translation': Link.project_id, 'annotation': Link.annotation_project_id, 'direct': Link.direct_conversation_id}


def schema_ready(db):
    inspector = inspect(db.connection())
    return all(inspector.has_table(name) for name in ('chat_session_category', 'chat_session_category_link'))


def require_ready(db):
    if not schema_ready(db):
        raise HTTPException(503, '团队会话分类尚未完成数据库迁移')


def serialize(row):
    return dict(id=str(row.id), name=row.name, active=row.active, revision=row.revision,
                updated_at=business_iso(row.updated_at))


def catalog(db, user):
    ready = schema_ready(db)
    hierarchy_ready = ready and folder_schema_ready(db)
    parents = {str(row.category_id): row.parent_key for row in db.query(Folder)} if hierarchy_ready else {}
    from discussion_chat_service import schema_ready as discussion_ready
    from discussion_chat_models import DiscussionMember
    rooms = {str(room) for room, in db.query(DiscussionMember.room_id).distinct()} if ready and discussion_ready(db) else set()
    return dict(ready=ready, hierarchy_ready=hierarchy_ready, can_manage=ready and can_manage_folders(db, user),
                items=[dict(serialize(row), parent_key=parents.get(str(row.id)), is_conversation=str(row.id) in rooms)
                       for row in db.query(Category).order_by(Category.created_at, Category.id)] if ready else [])


def validate_parent(db, parent_key, *, conversation=False):
    if not parent_key:
        return None
    if not folder_schema_ready(db):
        raise HTTPException(503, '二级目录尚未完成数据库迁移')
    key = str(parent_key)
    builtin = BUILTIN_INDEX.get(key)
    if builtin:
        if builtin['parentKey']:
            raise HTTPException(422, '最多只能建立两级目录')
        return key
    parent = db.query(Category).filter_by(id=parent_key).with_for_update().first()
    if not parent or not parent.active:
        raise HTTPException(422, '一级目录不存在或已停用')
    from discussion_chat_models import DiscussionMember
    from discussion_chat_service import schema_ready as discussion_ready
    if discussion_ready(db) and db.query(DiscussionMember.room_id).filter_by(room_id=parent.id).first():
        raise HTTPException(422, '会话下面不能创建目录或会话')
    location = db.get(Folder, parent.id)
    if location and location.parent_key:
        if not conversation:
            raise HTTPException(422, '最多只能建立两级目录')
        ancestor_key = str(location.parent_key)
        if ancestor_key not in BUILTIN_INDEX:
            ancestor = db.get(Category, UUID(ancestor_key))
            ancestor_location = db.get(Folder, UUID(ancestor_key))
            if not ancestor or not ancestor.active or (ancestor_location and ancestor_location.parent_key):
                raise HTTPException(422, '上级目录不存在、已停用或超过层级限制')
    return key


def validate_name(db, name, except_id=None, parent_key=None):
    normalized = name.strip()
    if not normalized or len(normalized) > 80:
        raise HTTPException(422, '分类名称须为1至80个字符')
    if normalized in SYSTEM_NAMES:
        raise HTTPException(409, '不能与系统会话筛选同名')
    # 保留旧库的全局唯一索引，避免上线前后名称冲突规则不一致。
    if any(row['id'] != str(except_id) and row['name'].casefold() == normalized.casefold() for row in BUILTIN_FOLDERS):
        raise HTTPException(409, '不能与内置目录同名')
    if parent_key == 'dcb1f917-6000-4000-8000-000000000002':
        from annotation_schemas import ANNOTATION_PROJECT_STATUS_LABELS
        if normalized in ANNOTATION_PROJECT_STATUS_LABELS.values():
            raise HTTPException(409, '不能与内置状态目录同名')
    if any(row.id != except_id and row.name.casefold() == normalized.casefold() for row in db.query(Category)):
        raise HTTPException(409, '已有同名团队分类（包含已停用分类）')
    return normalized


def require_manager(db, user):
    require_ready(db)
    if not can_manage_folders(db, user):
        raise HTTPException(403, '仅超级管理员和 Jimmy 可以新增或维护会话目录')


def protect_resource_discussion(db, category_id, active):
    if active is not False:
        return
    builtin = BUILTIN_INDEX.get(str(category_id))
    location = db.get(Folder, category_id) if folder_schema_ready(db) else None
    parent = builtin['parentKey'] if builtin else str(location.parent_key) if location else None
    resource_root = next(row['id'] for row in BUILTIN_FOLDERS if row['ruleKey'] == 'resource')
    if parent == resource_root:
        raise HTTPException(422, '资源开拓讨论会话只能修改名称，不能删除或停用')


def changed(db):
    # 事件不携带私聊ID或分类内容；每位接收者重新按自己的权限获取目录。
    broadcast_to_users([uid for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True))], {'type': 'chat_sessions_changed'})


def commit(db):
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, '已有同名团队分类，请重新检查名称') from error
    changed(db)


def require_category(db, category_id):
    row = db.query(Category).filter_by(id=category_id).with_for_update().first()
    if not row:
        raise HTTPException(404, '团队分类不存在')
    return row


def set_membership(db, user, kind, conversation_id, category_id, adding):
    require_ready(db)
    require_conversation(db, user, kind, conversation_id)
    category = require_category(db, category_id)
    if adding and not category.active:
        raise HTTPException(409, '团队分类已停用，请重新选择')
    if adding and folder_schema_ready(db):
        location = db.get(Folder, category.id)
        if location and location.parent_key and location.parent_key not in BUILTIN_INDEX:
            parent = db.get(Category, UUID(location.parent_key))
            if not parent or not parent.active:
                raise HTTPException(409, '一级目录已停用')
    column = TARGETS[kind]
    link = db.query(Link).filter(Link.category_id == category_id, column == conversation_id).first()
    if adding and not link:
        db.add(Link(category_id=category_id, updated_by=user.id, **{column.key: conversation_id}))
    elif not adding and link:
        db.delete(link)
    db.commit()
    changed(db)
    return dict(category_id=str(category_id), assigned=adding)


def require_conversation(db, user, kind, conversation_id):
    if kind == 'direct':
        import direct_chat_service
        direct_chat_service.require_project(db, conversation_id, user, lock=True)
    elif kind == 'annotation':
        import annotation_chat_service
        annotation_chat_service.require_project(db, conversation_id, user, lock=True)
    elif kind == 'translation':
        from chat_access_service import require_member
        require_member(db, kind, conversation_id, user)
        if not user_has_permission(db, user.id, 'projects:read'):
            raise HTTPException(403, '没有项目查看权限')
        if not db.query(TranslationProject).filter_by(id=conversation_id).with_for_update().first():
            raise HTTPException(404, '项目不存在')
    else:
        raise HTTPException(422, '不支持的会话类型')


def memberships(db, user, kind, conversation_id):
    require_ready(db)
    require_conversation(db, user, kind, conversation_id)
    return [str(cid) for cid, in db.query(Link.category_id).join(Category).filter(TARGETS[kind] == conversation_id, Category.active.is_(True))]


def decorate_sessions(db, rows):
    """只批量查询当前授权目录的关联，不补入被隐藏或未关注的会话。"""
    for row in rows:
        row['category_ids'] = row.get('category_ids', []) if row['kind'] == 'discussion' else []
    if not rows or not schema_ready(db):
        return
    by_key = {row['key']: row for row in rows}
    clauses = [column.in_([row['project_id'] for row in rows if row['kind'] == kind]) for kind, column in TARGETS.items()]
    links = db.query(Link).join(Category, Category.id == Link.category_id).filter(Category.active.is_(True), or_(*clauses)).all()
    for link in links:
        for kind, column in TARGETS.items():
            value = getattr(link, column.key)
            if value is not None and (row := by_key.get(f'{kind}:{value}')):
                row['category_ids'].append(str(link.category_id))
