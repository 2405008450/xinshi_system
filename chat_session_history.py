"""按参与人权限分页浏览全部会话，不依赖近期列表或关注状态。"""
from uuid import UUID

from sqlalchemy import String, case, cast, func, literal, select, union_all
from sqlalchemy.orm import aliased

from annotation_models import AnnotationProject
from chat_catalog_read import catalog_read
from chat_schema import phase_one_ready
from models import AppUser, ChatDirectConversation, ChatDirectMember, Client, TranslationProject
from chat_access_service import visible_ids
from search_matching import keyword_any
from permission_service import user_has_permission
import annotation_chat_service as annotation
import discussion_chat_service as discussion


def list_sessions(db, user, keyword='', offset=0, limit=30, mine=False):
    if not user.is_active:
        return dict(items=[], total=0)
    ready = phase_one_ready(db)
    queries = []
    protected_rooms = set()
    for kind, model, allowed in (
        ('annotation', AnnotationProject, annotation.can_view(db, user)),
        ('translation', TranslationProject, ready and user_has_permission(db, user.id, 'projects:read')),
    ):
        if allowed:
            query = select(literal(kind).label('kind'), cast(model.id, String).label('project_id'),
                model.project_name.label('title'), model.order_no.label('subtitle')).where(
                    model.id.in_(visible_ids(db, kind, user)))
            if kind == 'translation':
                client_name = func.coalesce(func.nullif(func.trim(Client.client_short_name), ''),
                                            func.nullif(func.trim(Client.client_name), ''))
                project_name = func.coalesce(model.project_name, '未命名项目')
                title = case((client_name.is_not(None), client_name + literal(' · ') + project_name),
                             else_=project_name)
                query = query.with_only_columns(literal(kind).label('kind'),
                    cast(model.id, String).label('project_id'), title.label('title'),
                    model.order_no.label('subtitle')).outerjoin(Client, Client.id == model.client_id)
            if mine:
                from chat_project_views import mine_condition
                query = query.where(mine_condition(db, kind, model, user))
            queries.append(query)
    if ready and not mine:
        peer = aliased(AppUser)
        direct = ChatDirectConversation
        peer_id = case((direct.user_low_id == user.id, direct.user_high_id), else_=direct.user_low_id)
        queries.append(select(literal('direct').label('kind'), cast(direct.id, String).label('project_id'),
            func.coalesce(peer.full_name, peer.username).label('title'), peer.department.label('subtitle'))
            .select_from(direct).join(peer, peer.id == peer_id)
            .join(ChatDirectMember, ChatDirectMember.conversation_id == direct.id).where(
                (direct.user_low_id == user.id) | (direct.user_high_id == user.id),
                ChatDirectMember.user_id == user.id, ChatDirectMember.hidden_at.is_(None)))
    if discussion.schema_ready(db):
        from discussion_chat_models import DiscussionMember
        rooms = discussion.visible_room_specs(db, user)
        if mine:
            from chat_project_views import owned_discussion_ids
            owned = owned_discussion_ids(db, user, [room['id'] for room in rooms])
            rooms = [room for room in rooms if room['id'] in owned]
        if rooms:
            protected_rooms = {room['id'] for room in rooms if room.get('deletion_protected')}
            name = case(*[(DiscussionMember.room_id == UUID(room['id']), room['name']) for room in rooms], else_='讨论群')
            queries.append(select(literal('discussion').label('kind'), cast(DiscussionMember.room_id, String).label('project_id'),
                name.label('title'), literal('讨论群').label('subtitle')).where(
                    DiscussionMember.user_id == user.id,
                    DiscussionMember.room_id.in_([UUID(room['id']) for room in rooms]),
                    DiscussionMember.room_id.in_(visible_ids(db, 'discussion', user))))
    if not queries:
        return dict(items=[], total=0)
    directory = union_all(*queries).subquery()
    query = select(directory)
    if keyword.strip():
        query = query.where(keyword_any([directory.c.title, directory.c.subtitle], keyword))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(directory.c.title, directory.c.kind, directory.c.project_id)
        .offset(offset).limit(limit)).mappings()
    items = []
    for row in rows:
        project_id = str(UUID(row['project_id']))
        item = dict(row, project_id=project_id, key=f"{row['kind']}:{project_id}")
        if row['kind'] == 'discussion':
            item['deletion_protected'] = project_id in protected_rooms
        items.append(item)
    return dict(items=items, total=total)


@catalog_read
def history_page(db, user, keyword='', offset=0, limit=30, mine=False):
    from chat_project_views import decorate_sessions
    from chat_session_category_service import decorate_sessions as decorate_categories
    from routers.chat_sessions import decorate_member_counts

    result = list_sessions(db, user, keyword, offset, limit, mine)
    items = result['items']
    for item in items:
        item['project_id'] = UUID(item['project_id'])
    decorate_sessions(db, user, items)
    decorate_member_counts(db, items)
    decorate_categories(db, items)
    return dict(result, offset=offset, limit=limit, has_more=offset + len(items) < result['total'])
