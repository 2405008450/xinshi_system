"""跨会话历史检索；所有分页和统计共用参与人及模块权限过滤。"""
from sqlalchemy import String, case, cast, func, literal, select, union_all
from sqlalchemy.orm import aliased
from uuid import UUID
from models import AppUser, ChatDirectConversation, ChatProjectMessage, ChatProjectEnabled, ChatProjectMessageFavorite, Client, SubClient
from annotation_models import AnnotationProject
from models import TranslationProject
from chat_access_service import visible_ids
from chat_time import api_time
from search_matching import keyword_any
from permission_service import user_has_permission
import annotation_chat_service as annotation
import discussion_chat_service as discussion
from discussion_chat_models import DiscussionMessage


def search_messages(db, user, keyword, *, offset=0, limit=30, favorites_only=False, tag_id=None):
    if not user.is_active or getattr(user,'is_deleted',False) or (not keyword.strip() and not favorites_only):
        return dict(items=[], total=0, has_more=False)
    message = ChatProjectMessage
    queries = []
    from chat_favorite_tags import require_ready,matches_tag,decorate
    if tag_id:
        require_ready(db)
        if not favorites_only:
            from fastapi import HTTPException
            raise HTTPException(422,'标签筛选仅用于消息收藏')

    def project_query(kind, model, column):
        query=select(cast(message.id, String).label('message_id'), literal(kind).label('project_type'),
            cast(column, String).label('project_id'), model.project_name.label('title'), model.order_no.label('subtitle'),
            message.sender_name, message.content, message.created_at).join(model, model.id == column).where(
                column.in_(visible_ids(db, kind, user)), message.message_type == 'user', message.recalled_at.is_(None),
                keyword_any([message.content, message.sender_name], keyword) if not favorites_only else True)
        if favorites_only:
            query=query.join(ChatProjectMessageFavorite,ChatProjectMessageFavorite.message_id==message.id).where(ChatProjectMessageFavorite.user_id==user.id)
            if tag_id:query=query.where(matches_tag(user.id,kind,column,message.id,tag_id))
            if keyword.strip():
                query=query.outerjoin(Client,Client.id==model.client_id).outerjoin(SubClient,SubClient.id==model.sub_client_id).where(keyword_any(
                    [message.content,message.sender_name,model.project_name,model.order_no,Client.client_name,Client.client_short_name,SubClient.client_name,SubClient.client_short_name],keyword))
        return query

    if annotation.can_view(db, user):
        queries.append(project_query('annotation', AnnotationProject, message.annotation_project_id))
    if user_has_permission(db, user.id, 'projects:read'):
        queries.append(project_query('translation', TranslationProject, message.project_id).join(
            ChatProjectEnabled, ChatProjectEnabled.project_id == message.project_id).where(ChatProjectEnabled.enabled.is_(True)))
    peer = aliased(AppUser)
    conversation = ChatDirectConversation
    peer_id = case((conversation.user_low_id == user.id, conversation.user_high_id), else_=conversation.user_low_id)
    direct_query=select(cast(message.id, String).label('message_id'), literal('direct').label('project_type'),
        cast(conversation.id, String).label('project_id'), func.coalesce(peer.full_name, peer.username).label('title'),
        literal('单聊').label('subtitle'), message.sender_name, message.content, message.created_at).join(
            conversation, conversation.id == message.direct_conversation_id).join(peer, peer.id == peer_id).where(
            (conversation.user_low_id == user.id) | (conversation.user_high_id == user.id),
            message.message_type == 'user', message.recalled_at.is_(None),
            keyword_any([message.content,message.sender_name,peer.full_name,peer.username] if favorites_only else [message.content,message.sender_name],keyword))
    if favorites_only:direct_query=direct_query.join(ChatProjectMessageFavorite,ChatProjectMessageFavorite.message_id==message.id).where(ChatProjectMessageFavorite.user_id==user.id)
    if tag_id:direct_query=direct_query.where(matches_tag(user.id,'direct',conversation.id,message.id,tag_id))
    queries.append(direct_query)
    if discussion.schema_ready(db):
        # 名称含内置讨论与自建会话；只有仍有效、当前用户有权访问的房间进入查询。
        rooms = [row for row in discussion.room_specs(db) if discussion.can_view_room(db, user, row)]
        if rooms:
            from uuid import UUID
            room_title = case(*[(DiscussionMessage.room_id == UUID(row['id']), row['name']) for row in rooms], else_='会话')
            discussion_time = func.timezone('Asia/Hong_Kong', DiscussionMessage.created_at) if db.get_bind().dialect.name == 'postgresql' else DiscussionMessage.created_at
            discussion_query=select(cast(DiscussionMessage.id, String).label('message_id'), literal('discussion').label('project_type'),
                cast(DiscussionMessage.room_id, String).label('project_id'), room_title.label('title'), literal('群聊').label('subtitle'),
                DiscussionMessage.sender_name, DiscussionMessage.content, discussion_time.label('created_at')).where(
                DiscussionMessage.room_id.in_([UUID(row['id']) for row in rooms]),
                DiscussionMessage.room_id.in_(visible_ids(db, 'discussion', user)), DiscussionMessage.recalled_at.is_(None),
                keyword_any([DiscussionMessage.content,DiscussionMessage.sender_name],keyword) if not favorites_only else True)
            if favorites_only:
                from discussion_chat_models import DiscussionMessageAction
                discussion_query=discussion_query.join(DiscussionMessageAction,DiscussionMessageAction.message_id==DiscussionMessage.id).where(
                    DiscussionMessageAction.user_id==user.id,DiscussionMessageAction.favorited_at.is_not(None))
                if tag_id:discussion_query=discussion_query.where(matches_tag(user.id,'discussion',DiscussionMessage.room_id,DiscussionMessage.id,tag_id))
                if keyword.strip():
                    metadata=_discussion_business_keywords(db,rooms)
                    business=case(*[(DiscussionMessage.room_id==UUID(rid),text) for rid,text in metadata.items()],else_='') if metadata else literal('')
                    discussion_query=discussion_query.where(keyword_any([DiscussionMessage.content,DiscussionMessage.sender_name,room_title,business],keyword))
            queries.append(discussion_query)
    results = union_all(*queries).subquery()
    total = db.scalar(select(func.count()).select_from(results))
    rows = db.execute(select(results).order_by(results.c.created_at.desc(), results.c.project_type,
        results.c.message_id.desc()).offset(offset).limit(limit)).mappings()
    items = [dict(message_id=str(UUID(row['message_id'])) if row['project_type']!='discussion' else row['message_id'], project_id=str(UUID(row['project_id'])), project_type=row['project_type'],
        key=f"{row['project_type']}:{UUID(row['project_id'])}", title=row['title'] or '会话', subtitle=row['subtitle'] or '',
        sender_name=row['sender_name'], preview=' '.join(row['content'].split())[:500], created_at=api_time(row['created_at'])) for row in rows]
    if favorites_only:decorate(db,user.id,items)
    return dict(items=items, total=total, has_more=offset + len(items) < total)


def _discussion_business_keywords(db,rooms):
    """仅给已通过房间权限过滤的消息提供关联项目/客户搜索字段。"""
    from chat_project_views import discussion_sources,MODELS
    sources=discussion_sources(db,[row['id'] for row in rooms]); metadata={}
    for kind,model in MODELS.items():
        ids={pid for module,pid in sources.values() if module==kind}
        if not ids:continue
        columns=[model.id,model.project_name,model.order_no]
        query=db.query(*columns,Client.client_name,Client.client_short_name,SubClient.client_name,SubClient.client_short_name).outerjoin(
            Client,Client.id==model.client_id).outerjoin(SubClient,SubClient.id==model.sub_client_id).filter(model.id.in_(ids))
        for row in query:metadata[(kind,row[0])]=' '.join(str(value) for value in row[1:] if value)
    return {rid:metadata.get(source,'') for rid,source in sources.items()}
