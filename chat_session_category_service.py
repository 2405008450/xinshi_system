"""团队归类共享，授权和目录范围始终由原会话决定。"""
from fastapi import HTTPException
from sqlalchemy import inspect, or_
from sqlalchemy.exc import IntegrityError
from business_time import business_iso
from models import AppUser, TranslationProject
from permission_service import user_has_permission
from notification_ws import broadcast_to_users
from chat_session_category_models import ChatSessionCategory as Category, ChatSessionCategoryLink as Link

SYSTEM_NAMES = frozenset(('消息', '置顶', '未读', '@我', '单聊', '特别关注', '项目群', '标注项目群', '笔译项目群', '我创建的'))
TARGETS = {'translation': Link.project_id, 'annotation': Link.annotation_project_id, 'direct': Link.direct_conversation_id}


def schema_ready(db):
    inspector = inspect(db.get_bind())
    return all(inspector.has_table(name) for name in ('chat_session_category', 'chat_session_category_link'))


def require_ready(db):
    if not schema_ready(db):
        raise HTTPException(503, '团队会话分类尚未完成数据库迁移')


def serialize(row):
    return dict(id=str(row.id), name=row.name, active=row.active, revision=row.revision,
                updated_at=business_iso(row.updated_at))


def catalog(db, user):
    ready = schema_ready(db)
    return dict(ready=ready, can_manage=ready and user_has_permission(db, user.id, 'chat_topics:manage'),
                items=[serialize(row) for row in db.query(Category).order_by(Category.created_at, Category.id)] if ready else [])


def validate_name(db, name, except_id=None):
    normalized = name.strip()
    if not normalized or len(normalized) > 80:
        raise HTTPException(422, '分类名称须为1至80个字符')
    if normalized in SYSTEM_NAMES:
        raise HTTPException(409, '不能与系统会话筛选同名')
    if any(row.id != except_id and row.name.casefold() == normalized.casefold() for row in db.query(Category)):
        raise HTTPException(409, '已有同名团队分类（包含已停用分类）')
    return normalized


def require_manager(db, user):
    require_ready(db)
    if not user_has_permission(db, user.id, 'chat_topics:manage'):
        raise HTTPException(403, '没有团队分类维护权限')


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
    category = require_category(db, category_id)
    if adding and not category.active:
        raise HTTPException(409, '团队分类已停用，请重新选择')
    require_conversation(db, user, kind, conversation_id)
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
        row['category_ids'] = []
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
