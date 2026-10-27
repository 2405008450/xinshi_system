"""当前用户的历史提及收件箱；阅读位置只影响未读标记，不影响列表。"""
from search_matching import keyword_ilike, keyword_or
from sqlalchemy import and_, case, false, func, literal, or_

import annotation_chat_service as annotation
from annotation_models import AnnotationProject
from chat_schema import phase_one_ready
from chat_time import api_time
from models import (AnnotationChatMember, ChatProjectEnabled, ChatProjectMemberPref,
                    ChatProjectMessage, ChatProjectMention, TranslationProject)


def mention_query(db, user, keyword='', *, project_type=None, project_status=None, project_id=None):
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
    from chat_access_service import visible_ids
    query = query.filter(or_(and_(AnnotationProject.id.is_not(None), AnnotationChatMember.user_id == user.id),
                            and_(TranslationProject.id.in_(visible_ids(db, 'translation', user)), ChatProjectEnabled.enabled.is_(True))))
    if project_type == 'annotation':
        query = query.filter(annotation_scope)
    elif project_type == 'translation':
        query = query.filter(message.project_id.is_not(None))
    if project_id is not None:
        project_column = message.annotation_project_id if project_type == 'annotation' else message.project_id
        query = query.filter(project_column == project_id)
    if project_status:
        # 按项目当前状态筛选历史提及；总数与游标分页共用同一查询。
        query = query.filter(AnnotationProject.project_status == project_status)
    if keyword.strip():
        pattern = '%' + keyword.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(keyword_or(lambda _search_part: or_(*(keyword_ilike(column, _search_part, escape='\\') for column in
                                  (title, subtitle, message.sender_name, message.content))), pattern))
    return query


def mention_count(db, user):
    return db.query(func.count()).select_from(history_query(db,user)).scalar() or 0


def annotation_mention_counts(db, user):
    """按项目汇总当前用户的有效历史提及，供会话目录逐层筛选使用。"""
    project_id = ChatProjectMessage.annotation_project_id
    rows = mention_query(db, user, project_type='annotation').with_entities(
        project_id, func.count(ChatProjectMessage.id)).group_by(project_id).all()
    return [dict(project_id=pid, count=count) for pid, count in rows]


def history_query(db,user,keyword='',*,project_type=None,project_status=None,project_id=None):
    from datetime import datetime
    from sqlalchemy import String, cast, select, union_all
    from models import AppUser, ChatDirectConversation, ChatDirectMember
    sources=[]
    if project_type in (None,'annotation','translation'):
        query=mention_query(db,user,keyword,project_type=project_type,project_status=project_status,project_id=project_id)
        # 三类消息统一使用香港本地业务时间，排序与游标不依赖服务器时区。
        for_kind=case((ChatProjectMessage.annotation_project_id.is_not(None),literal('annotation')),else_=literal('translation'))
        pid=case((ChatProjectMessage.annotation_project_id.is_not(None),ChatProjectMessage.annotation_project_id),else_=ChatProjectMessage.project_id)
        sources.append(query.with_entities(cast(ChatProjectMessage.id,String).label('message_id'),cast(pid,String).label('project_id'),for_kind.label('kind'),
            case((ChatProjectMessage.annotation_project_id.is_not(None),AnnotationProject.project_name),else_=TranslationProject.project_name).label('title'),
            case((ChatProjectMessage.annotation_project_id.is_not(None),AnnotationProject.order_no),else_=TranslationProject.order_no).label('subtitle'),
            ChatProjectMessage.sender_name.label('sender_name'),ChatProjectMessage.content.label('content'),ChatProjectMessage.created_at.label('stamp'),ChatProjectMessage.sequence_no.label('sequence_no'),
            (ChatProjectMessage.sequence_no>case((ChatProjectMessage.annotation_project_id.is_not(None),func.coalesce(AnnotationChatMember.last_read_sequence,0)),else_=func.coalesce(ChatProjectMemberPref.last_read_sequence,0) if phase_one_ready(db) else literal(0))).label('unread')).statement)
    if project_type in (None,'direct') and not project_status and phase_one_ready(db):
        message=ChatProjectMessage
        query=db.query(message).join(ChatProjectMention,ChatProjectMention.message_id==message.id).join(ChatDirectConversation,ChatDirectConversation.id==message.direct_conversation_id).join(ChatDirectMember,and_(ChatDirectMember.conversation_id==ChatDirectConversation.id,ChatDirectMember.user_id==user.id)).filter(ChatProjectMention.mentioned_user_id==user.id,message.recalled_at.is_(None),or_(ChatDirectConversation.user_low_id==user.id,ChatDirectConversation.user_high_id==user.id))
        if project_id:query=query.filter(message.direct_conversation_id==project_id)
        if keyword.strip():
            from search_matching import keyword_contains
            query=query.filter(or_(*[keyword_contains(column,keyword) for column in (message.content,message.sender_name)]))
        sources.append(query.with_entities(cast(message.id,String).label('message_id'),cast(message.direct_conversation_id,String).label('project_id'),literal('direct').label('kind'),literal('私聊').label('title'),literal('').label('subtitle'),message.sender_name.label('sender_name'),message.content.label('content'),message.created_at.label('stamp'),message.sequence_no.label('sequence_no'),(message.sequence_no>ChatDirectMember.last_read_sequence).label('unread')).statement)
    from discussion_mentions import ready
    if project_type in (None,'discussion') and not project_status and ready(db):
        import discussion_chat_service as discussion
        from discussion_chat_models import DiscussionMessage as Message, DiscussionMention as Mention, DiscussionMember as Member
        from chat_session_category_models import ChatSessionCategory
        room_specs=discussion.room_specs(db)
        resource_visible=discussion.can_view(db,user)
        visible=[__import__('uuid').UUID(room['id']) for room in room_specs if room.get('parent_key',discussion.RESOURCE_ROOT)!=discussion.RESOURCE_ROOT or resource_visible]
        query=db.query(Message).join(Mention,Mention.message_id==Message.id).join(Member,and_(Member.room_id==Message.room_id,Member.user_id==user.id)).outerjoin(ChatSessionCategory,ChatSessionCategory.id==Message.room_id).filter(Mention.user_id==user.id,Message.room_id.in_(visible),Message.recalled_at.is_(None))
        if project_id:query=query.filter(Message.room_id==project_id)
        titles={__import__('uuid').UUID(room['id']):room['name'] for room in room_specs}
        title=func.coalesce(ChatSessionCategory.name,case(titles,value=Message.room_id,else_=literal('讨论会话')))
        if keyword.strip():
            from search_matching import keyword_contains
            query=query.filter(or_(*[keyword_contains(column,keyword) for column in (title,Message.content,Message.sender_name)]))
        stamp=func.timezone('Asia/Hong_Kong',Message.created_at) if db.get_bind().dialect.name=='postgresql' else Message.created_at
        sources.append(query.with_entities(cast(Message.id,String).label('message_id'),cast(Message.room_id,String).label('project_id'),literal('discussion').label('kind'),title.label('title'),literal('讨论会话').label('subtitle'),Message.sender_name.label('sender_name'),Message.content.label('content'),stamp.label('stamp'),Message.id.label('sequence_no'),(Message.id>Member.last_read_id).label('unread')).statement)
    if not sources:
        sources=[select(literal('').label('message_id'),literal('').label('project_id'),literal('').label('kind'),literal('').label('title'),literal('').label('subtitle'),literal('').label('sender_name'),literal('').label('content'),literal(datetime(1970,1,1)).label('stamp'),literal(0).label('sequence_no'),literal(False).label('unread')).where(false())]
    return union_all(*sources).subquery()


def mention_session_statistics(db, user):
    """目录总数、分组计数和排序时间共用一次权限过滤及聚合。"""
    table = history_query(db, user)
    from uuid import UUID
    return {(kind, str(UUID(pid))): (count, stamp) for kind, pid, count, stamp in db.query(
        table.c.kind, table.c.project_id, func.count(), func.max(table.c.stamp)
    ).group_by(table.c.kind, table.c.project_id).all()}


def decorate_mention_sessions(db, user, rows, stats=None):
    """只为当前可见目录补充个人提及时间与客户，普通消息不会改变提及排序。"""
    if stats is None:
        stats = mention_session_statistics(db, user)
    from models import Client
    customers = {}
    for kind, model in [('annotation', AnnotationProject), ('translation', TranslationProject)]:
        ids = [row['project_id'] for row in rows if row['kind'] == kind]
        if ids:
            customers.update({(kind, str(pid)): short or name or '' for pid, short, name in db.query(
                model.id, Client.client_short_name, Client.client_name
            ).outerjoin(Client, Client.id == model.client_id).filter(model.id.in_(ids)).all()})
    for row in rows:
        key = (row['kind'], str(row['project_id']))
        count, stamp = stats.get(key, (0, None))
        row.update(mention_history_count=count, latest_mention_at=api_time(stamp), customer_name=customers.get(key, ''))


def list_mentions(db, user, *, keyword='', before=None, limit=50, project_type=None, project_status=None, project_id=None, sort='time_desc'):
    import base64,json
    from datetime import datetime
    from uuid import UUID
    from fastapi import HTTPException
    table=history_query(db,user,keyword,project_type=project_type,project_status=project_status,project_id=project_id)
    from sqlalchemy import String, cast, select
    from models import Client
    # 关联真实客户字段；无客户的讨论和私聊排在客户项目之后。
    names = []
    for kind, model in [('annotation', AnnotationProject), ('translation', TranslationProject)]:
        name = select(func.coalesce(func.nullif(Client.client_short_name, ''), Client.client_name, '')).select_from(model).outerjoin(
            Client, Client.id == model.client_id).where(cast(model.id, String) == table.c.project_id).scalar_subquery()
        names.append((table.c.kind == kind, name))
    table = db.query(table, func.coalesce(case(*names, else_=''), '').label('customer_name')).subquery()
    query=db.query(table)
    total=query.count()
    ascending = sort == 'time_asc'
    customer_sort = sort.startswith('customer_')
    if sort not in ('time_desc', 'time_asc', 'customer_asc', 'customer_desc'):
        raise HTTPException(422, '无效的提及排序')
    # 未读始终优先；仅在未读/已读分区内部改变客户与时间排序。
    unread_order = case((table.c.unread, 1), else_=0)
    columns = [unread_order, table.c.stamp, table.c.kind, table.c.sequence_no]
    directions = [False, ascending, ascending, ascending]
    values_from = lambda row: [int(bool(row.unread)), row.stamp.isoformat(), row.kind, row.sequence_no]
    if customer_sort:
        columns = [unread_order, case((table.c.customer_name == '', 1), else_=0), table.c.customer_name, table.c.stamp, table.c.kind, table.c.sequence_no]
        directions = [False, True, sort == 'customer_asc', False, False, False]
        values_from = lambda row: [int(bool(row.unread)), int(not row.customer_name), row.customer_name, row.stamp.isoformat(), row.kind, row.sequence_no]
    if before is not None:
        token=str(before)
        if token.isdecimal():query=query.filter(table.c.sequence_no<int(token))
        else:
            try:
                decoded=json.loads(base64.urlsafe_b64decode(token[3:].encode()).decode())
                if token.startswith('v2.') and sort == 'time_desc': values=[0, *decoded]
                elif token.startswith('v3.') and decoded[0] == sort: values=decoded[1:]
                else: raise ValueError()
                if len(values) != len(columns): raise ValueError()
                values[-3]=datetime.fromisoformat(values[-3]);values[-1]=int(values[-1])
            except Exception as exc:raise HTTPException(422,'无效的提及分页游标') from exc
            query=query.filter(or_(*(and_(*[columns[j] == values[j] for j in range(i)], column > values[i] if directions[i] else column < values[i]) for i, column in enumerate(columns))))
    rows=query.order_by(*[column.asc() if asc else column.desc() for column, asc in zip(columns, directions)]).limit(limit+1).all()
    items=[]
    for row in rows[:limit]:
        pid=UUID(row.project_id)
        items.append(dict(message_id=str(row.message_id) if row.kind=='discussion' else UUID(row.message_id),sequence_no=row.sequence_no,key=f'{row.kind}:{pid}',project_id=pid,project_type=row.kind,title=row.title or '未命名会话',subtitle=row.subtitle or '',sender_name=row.sender_name,preview=' '.join((row.content or '').split())[:500] or '[附件]',created_at=api_time(row.stamp),unread=bool(row.unread)))
    has_more=len(rows)>limit
    cursor=None
    if has_more and items:
        last=rows[limit-1];cursor='v3.'+base64.urlsafe_b64encode(json.dumps([sort, *values_from(last)]).encode()).decode()
    return dict(items=items,total=total,has_more=has_more,next_before=cursor)
