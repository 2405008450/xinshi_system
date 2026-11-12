"""会话参与人边界；关注、置顶和项目查看权限不能代替参与人资格。"""
from fastapi import HTTPException
from models import AnnotationChatMember, ChatProjectMemberPref, AppUser
from discussion_chat_models import DiscussionMember


MEMBERS = {
    'annotation': (AnnotationChatMember, AnnotationChatMember.project_id),
    'translation': (ChatProjectMemberPref, ChatProjectMemberPref.project_id),
    'discussion': (DiscussionMember, DiscussionMember.room_id),
}


def visible_ids(db, kind, user):
    model, column = MEMBERS[kind]
    query=db.query(column).filter(model.user_id == user.id)
    if kind=='discussion':
        from technical_task_conversations import restricted_ids
        from technical_task_conversations import can_access
        if not can_access(db,user): query=query.filter(column.notin_(restricted_ids(db)))
    return query


def member_ids(db, kind, conversation_id):
    model, column = MEMBERS[kind]
    query=db.query(model.user_id).filter(column == conversation_id)
    if kind=='discussion':
        from technical_task_conversations import restricted_ids,eligible
        if conversation_id in restricted_ids(db): query=query.filter(model.user_id.in_(eligible(db).with_entities(AppUser.id)))
    return {uid for uid, in query}


def is_member(db, kind, conversation_id, user):
    if not user or not user.is_active:
        return False
    if kind=='discussion':
        from technical_task_conversations import restricted_ids
        from technical_task_conversations import can_access
        if conversation_id in restricted_ids(db) and not can_access(db,user): return False
    model, column = MEMBERS[kind]
    return db.query(model.user_id).filter(column == conversation_id, model.user_id == user.id).first() is not None


def require_member(db, kind, conversation_id, user):
    if not is_member(db, kind, conversation_id, user):
        raise HTTPException(404, '会话不存在或你不是该会话参与人')


def invite_mentioned_users(db, kind, conversation_id, actor, targets, baseline=0):
    """兼容旧调用名称，仅校验成员资格；提及不得隐式邀请入群。"""
    require_member(db, kind, conversation_id, actor)
    existing = member_ids(db, kind, conversation_id)
    if any(target.id not in existing for target in targets):
        raise ValueError('只能提及当前会话成员，请先通过添加成员邀请入群')
    import annotation_chat_service as annotation
    if any(not annotation.can_view(db, target) for target in targets):
        raise ValueError('被提及的用户已停用或没有项目沟通权限')
