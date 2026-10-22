"""会话参与人边界；关注、置顶和项目查看权限不能代替参与人资格。"""
from fastapi import HTTPException
from models import AnnotationChatMember, ChatProjectMemberPref
from discussion_chat_models import DiscussionMember


MEMBERS = {
    'annotation': (AnnotationChatMember, AnnotationChatMember.project_id),
    'translation': (ChatProjectMemberPref, ChatProjectMemberPref.project_id),
    'discussion': (DiscussionMember, DiscussionMember.room_id),
}


def visible_ids(db, kind, user):
    model, column = MEMBERS[kind]
    return db.query(column).filter(model.user_id == user.id)


def member_ids(db, kind, conversation_id):
    model, column = MEMBERS[kind]
    return {uid for uid, in db.query(model.user_id).filter(column == conversation_id)}


def is_member(db, kind, conversation_id, user):
    if not user or not user.is_active:
        return False
    model, column = MEMBERS[kind]
    return db.query(model.user_id).filter(column == conversation_id, model.user_id == user.id).first() is not None


def require_member(db, kind, conversation_id, user):
    if not is_member(db, kind, conversation_id, user):
        raise HTTPException(404, '会话不存在或你不是该会话参与人')


def invite_mentioned_users(db, kind, conversation_id, actor, targets, baseline=0):
    """显式提及的非成员在消息事务内加入；发信失败时一并回滚。"""
    require_member(db, kind, conversation_id, actor)
    import annotation_chat_service as annotation
    if any(not annotation.can_view(db, target) for target in targets):
        raise ValueError('被提及的用户已停用或没有项目沟通权限')
    existing = member_ids(db, kind, conversation_id)
    for target in targets:
        if target.id in existing:
            continue
        if kind == 'annotation':
            annotation.add_member(db, conversation_id, target.id, baseline=baseline)
        else:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            insert_member = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
            db.execute(insert_member(ChatProjectMemberPref).values(project_id=conversation_id, user_id=target.id,
                last_read_sequence=baseline, pinned=False, starred=False).on_conflict_do_nothing())
    db.flush()
