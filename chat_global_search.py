"""跨会话历史检索；所有分页和统计共用参与人及模块权限过滤。"""
from sqlalchemy import String, case, cast, func, literal, select, union_all
from sqlalchemy.orm import aliased
from models import AppUser, ChatDirectConversation, ChatProjectMessage, ChatProjectEnabled
from annotation_models import AnnotationProject
from models import TranslationProject
from chat_access_service import visible_ids
from chat_time import api_time
from search_matching import keyword_any
from permission_service import user_has_permission
import annotation_chat_service as annotation
import discussion_chat_service as discussion
from discussion_chat_models import DiscussionMessage


def search_messages(db, user, keyword, *, offset=0, limit=30):
    if not user.is_active or not keyword.strip():
        return dict(items=[], total=0, has_more=False)
    message = ChatProjectMessage
    queries = []

    def project_query(kind, model, column):
        return select(cast(message.id, String).label('message_id'), literal(kind).label('project_type'),
            cast(column, String).label('project_id'), model.project_name.label('title'), model.order_no.label('subtitle'),
            message.sender_name, message.content, message.created_at).join(model, model.id == column).where(
                column.in_(visible_ids(db, kind, user)), message.message_type == 'user', message.recalled_at.is_(None),
                keyword_any([message.content, message.sender_name], keyword))

    if annotation.can_view(db, user):
        queries.append(project_query('annotation', AnnotationProject, message.annotation_project_id))
    if user_has_permission(db, user.id, 'projects:read'):
        queries.append(project_query('translation', TranslationProject, message.project_id).join(
            ChatProjectEnabled, ChatProjectEnabled.project_id == message.project_id).where(ChatProjectEnabled.enabled.is_(True)))
    peer = aliased(AppUser)
    conversation = ChatDirectConversation
    peer_id = case((conversation.user_low_id == user.id, conversation.user_high_id), else_=conversation.user_low_id)
    queries.append(select(cast(message.id, String).label('message_id'), literal('direct').label('project_type'),
        cast(conversation.id, String).label('project_id'), func.coalesce(peer.full_name, peer.username).label('title'),
        literal('单聊').label('subtitle'), message.sender_name, message.content, message.created_at).join(
            conversation, conversation.id == message.direct_conversation_id).join(peer, peer.id == peer_id).where(
            (conversation.user_low_id == user.id) | (conversation.user_high_id == user.id),
            message.message_type == 'user', message.recalled_at.is_(None),
            keyword_any([message.content, message.sender_name], keyword)))
    if discussion.schema_ready(db):
        # 名称含内置讨论与自建会话；只有仍有效、当前用户有权访问的房间进入查询。
        rooms = [row for row in discussion.room_specs(db) if discussion.can_view_room(db, user, row)]
        if rooms:
            from uuid import UUID
            room_title = case(*[(DiscussionMessage.room_id == UUID(row['id']), row['name']) for row in rooms], else_='会话')
            discussion_time = func.timezone('Asia/Hong_Kong', DiscussionMessage.created_at) if db.get_bind().dialect.name == 'postgresql' else DiscussionMessage.created_at
            queries.append(select(cast(DiscussionMessage.id, String).label('message_id'), literal('discussion').label('project_type'),
                cast(DiscussionMessage.room_id, String).label('project_id'), room_title.label('title'), literal('群聊').label('subtitle'),
                DiscussionMessage.sender_name, DiscussionMessage.content, discussion_time.label('created_at')).where(
                DiscussionMessage.room_id.in_([UUID(row['id']) for row in rooms]),
                DiscussionMessage.room_id.in_(visible_ids(db, 'discussion', user)), DiscussionMessage.recalled_at.is_(None),
                keyword_any([DiscussionMessage.content, DiscussionMessage.sender_name], keyword)))
    results = union_all(*queries).subquery()
    total = db.scalar(select(func.count()).select_from(results))
    rows = db.execute(select(results).order_by(results.c.created_at.desc(), results.c.project_type,
        results.c.message_id.desc()).offset(offset).limit(limit)).mappings()
    items = [dict(message_id=row['message_id'], project_id=row['project_id'], project_type=row['project_type'],
        key=f"{row['project_type']}:{row['project_id']}", title=row['title'] or '会话', subtitle=row['subtitle'] or '',
        sender_name=row['sender_name'], preview=' '.join(row['content'].split())[:500], created_at=api_time(row['created_at'])) for row in rows]
    return dict(items=items, total=total, has_more=offset + len(items) < total)
