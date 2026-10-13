"""当前用户的历史提及收件箱；阅读位置只影响未读标记，不影响列表。"""
from sqlalchemy import and_, case, false, func, literal, or_

import annotation_chat_service as annotation
from annotation_models import AnnotationProject
from chat_schema import phase_one_ready
from chat_time import api_time
from models import (AnnotationChatMember, ChatProjectEnabled, ChatProjectMemberPref,
                    ChatProjectMessage, ChatProjectMention, TranslationProject)


def mention_query(db, user, keyword='', *, project_type=None, project_status=None):
    message = ChatProjectMessage
    ready = phase_one_ready(db)
    annotation_scope = message.annotation_project_id.is_not(None)
    read_sequence = func.coalesce(AnnotationChatMember.last_read_sequence, 0)
    translation_read = literal(0)
    query = db.query(message).join(ChatProjectMention, ChatProjectMention.message_id == message.id)
    query = query.outerjoin(AnnotationProject, AnnotationProject.id == message.annotation_project_id).outerjoin(
        TranslationProject, TranslationProject.id == message.project_id).outerjoin(
        ChatProjectEnabled, ChatProjectEnabled.project_id == message.project_id).outerjoin(
        AnnotationChatMember, and_(AnnotationChatMember.project_id == message.annotation_project_id,
                                  AnnotationChatMember.user_id == user.id))
    if ready:
        query = query.outerjoin(ChatProjectMemberPref, and_(ChatProjectMemberPref.project_id == message.project_id,
                                                           ChatProjectMemberPref.user_id == user.id))
        translation_read = func.coalesce(ChatProjectMemberPref.last_read_sequence, 0)
    title = case((annotation_scope, AnnotationProject.project_name), else_=TranslationProject.project_name)
    subtitle = case((annotation_scope, AnnotationProject.order_no), else_=TranslationProject.order_no)
    query = query.add_columns(
        case((annotation_scope, literal('annotation')), else_=literal('translation')).label('kind'),
        title.label('title'), subtitle.label('subtitle'),
        (message.sequence_no > case((annotation_scope, read_sequence), else_=translation_read)).label('unread'),
    ).filter(ChatProjectMention.mentioned_user_id == user.id, message.message_type == 'user',
             message.recalled_at.is_(None))
    # 沿用各会话的查看权限与笔译群启用规则；退订不会删除有权查看的历史提及。
    if not annotation.can_view(db, user):
        return query.filter(false())
    query = query.filter(or_(AnnotationProject.id.is_not(None),
                            and_(TranslationProject.id.is_not(None), ChatProjectEnabled.enabled.is_(True))))
    if project_type == 'annotation':
        query = query.filter(annotation_scope)
    elif project_type == 'translation':
        query = query.filter(message.project_id.is_not(None))
    if project_status:
        # 按项目当前状态筛选历史提及；总数与游标分页共用同一查询。
        query = query.filter(AnnotationProject.project_status == project_status)
    if keyword.strip():
        pattern = '%' + keyword.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(or_(*(column.ilike(pattern, escape='\\') for column in
                                  (title, subtitle, message.sender_name, message.content))))
    return query


def mention_count(db, user):
    return mention_query(db, user).with_entities(ChatProjectMessage.id).count()


def list_mentions(db, user, *, keyword='', before=None, limit=50, project_type=None, project_status=None):
    query = mention_query(db, user, keyword, project_type=project_type, project_status=project_status)
    total = query.with_entities(ChatProjectMessage.id).count()
    if before is not None:
        query = query.filter(ChatProjectMessage.sequence_no < before)
    rows = query.order_by(ChatProjectMessage.sequence_no.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    items = []
    for message, kind, title, subtitle, unread in rows[:limit]:
        project_id = message.annotation_project_id if kind == 'annotation' else message.project_id
        items.append(dict(message_id=message.id, sequence_no=message.sequence_no,
                          key=f'{kind}:{project_id}', project_id=project_id, project_type=kind,
                          title=title or '未命名项目', subtitle=subtitle or '', sender_name=message.sender_name,
                          preview=' '.join(message.content.split())[:500] or '[附件]',
                          created_at=api_time(message.created_at), unread=bool(unread)))
    return dict(items=items, total=total, has_more=has_more,
                next_before=items[-1]['sequence_no'] if has_more else None)
