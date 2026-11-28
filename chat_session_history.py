"""按参与人权限分页浏览全部会话，不依赖近期列表或关注状态。"""
from uuid import UUID

from sqlalchemy import String, case, cast, func, literal, select, union_all
from sqlalchemy.orm import aliased

from annotation_models import AnnotationProject
from models import AppUser, ChatDirectConversation, TranslationProject, AnnotationChatMember, ChatProjectMemberPref, ChatDirectMember
from chat_schema import phase_one_ready
from chat_access_service import visible_ids
from search_matching import keyword_any
from permission_service import user_has_permission
import annotation_chat_service as annotation
import discussion_chat_service as discussion


def list_sessions(db, user, keyword='', offset=0, limit=30, mine=False, groups_only=False):
    if not user.is_active:
        return dict(items=[], total=0)
    queries = []
    ready = phase_one_ready(db)
    def preference(member, id_column, target, field):
        if not ready:
            return literal(False).label(field)
        return func.coalesce(select(getattr(member, field)).where(
            id_column == target, member.user_id == user.id).scalar_subquery(), False).label(field)
    for kind, model, allowed in (
        ('annotation', AnnotationProject, annotation.can_view(db, user)),
        ('translation', TranslationProject, user_has_permission(db, user.id, 'projects:read')),
    ):
        if allowed:
            member = AnnotationChatMember if kind == 'annotation' else ChatProjectMemberPref
            query = select(literal(kind).label('kind'), cast(model.id, String).label('project_id'),
                model.project_name.label('title'), model.order_no.label('subtitle'),
                preference(member, member.project_id, model.id, 'pinned'),
                preference(member, member.project_id, model.id, 'starred')).where(
                    model.id.in_(visible_ids(db, kind, user)))
            if mine:
                from chat_project_views import mine_condition
                query = query.where(mine_condition(db, kind, model, user))
            queries.append(query)
    peer = aliased(AppUser)
    direct = ChatDirectConversation
    peer_id = case((direct.user_low_id == user.id, direct.user_high_id), else_=direct.user_low_id)
    queries.append(select(literal('direct').label('kind'), cast(direct.id, String).label('project_id'),
        func.coalesce(peer.full_name, peer.username).label('title'), literal('私聊').label('subtitle'),
        preference(ChatDirectMember, ChatDirectMember.conversation_id, direct.id, 'pinned'),
        preference(ChatDirectMember, ChatDirectMember.conversation_id, direct.id, 'starred'))
        .select_from(direct).join(peer, peer.id == peer_id).where(
            ((direct.user_low_id == user.id) | (direct.user_high_id == user.id)) & ~literal(mine or groups_only)))
    if discussion.schema_ready(db):
        from discussion_chat_models import DiscussionMember
        rooms = [room for room in discussion.room_specs(db) if discussion.can_view_room(db, user, room)]
        if mine:
            from chat_project_views import owned_discussion_ids
            owned = owned_discussion_ids(db, user, [room['id'] for room in rooms])
            rooms = [room for room in rooms if room['id'] in owned]
        if rooms:
            name = case(*[(DiscussionMember.room_id == UUID(room['id']), room['name']) for room in rooms], else_='讨论群')
            queries.append(select(literal('discussion').label('kind'), cast(DiscussionMember.room_id, String).label('project_id'),
                name.label('title'), literal('讨论群').label('subtitle'),
                func.coalesce(DiscussionMember.pinned, False).label('pinned'),
                func.coalesce(DiscussionMember.starred, False).label('starred')).where(
                    DiscussionMember.user_id == user.id,
                    DiscussionMember.room_id.in_([UUID(room['id']) for room in rooms]),
                    DiscussionMember.room_id.in_(visible_ids(db, 'discussion', user))))
    directory = union_all(*queries).subquery()
    query = select(directory)
    if keyword.strip():
        query = query.where(keyword_any([directory.c.title, directory.c.subtitle], keyword))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(directory.c.pinned.desc(), directory.c.title, directory.c.kind, directory.c.project_id)
        .offset(offset).limit(limit)).mappings()
    return dict(items=[dict(row, project_id=str(UUID(row['project_id'])), key=f"{row['kind']}:{UUID(row['project_id'])}") for row in rows], total=total)
