"""按需搜索会话目录，仅为当前页补充详情，不读取历史消息正文。"""
from uuid import UUID

from chat_schema import phase_one_ready
from models import AppUser, ChatDirectConversation, TranslationProject
from annotation_models import AnnotationProject


def history_page(db, user, keyword='', offset=0, limit=30):
    from routers.chat_sessions import (annotation_sessions_query, translation_sessions_query,
                                      direct_sessions_query, decorate_member_counts)
    import annotation_chat_service as annotation
    import discussion_chat_service as discussions
    import chat_session_category_service as categories
    from discussion_chat_models import DiscussionMember

    ready = phase_one_ready(db)
    rows = []
    if annotation.can_view(db, user):
        for pid, title, order_no, status in annotation_sessions_query(db, user, ready).with_entities(
                AnnotationProject.id, AnnotationProject.project_name,
                AnnotationProject.order_no, AnnotationProject.project_status):
            rows.append(dict(key=f'annotation:{pid}', kind='annotation', project_id=pid,
                             title=title or '未命名项目', subtitle=order_no, project_status=status))
        if ready:
            from models import Client
            query = translation_sessions_query(db, user).outerjoin(Client, Client.id == TranslationProject.client_id)
            for pid, title, order_no, short, name in query.with_entities(
                    TranslationProject.id, TranslationProject.project_name, TranslationProject.order_no,
                    Client.client_short_name, Client.client_name):
                rows.append(dict(key=f'translation:{pid}', kind='translation', project_id=pid,
                    title=' · '.join(part for part in ((short or name or '').strip(), title or '未命名项目') if part),
                    subtitle=order_no))
    if ready:
        conversations = direct_sessions_query(db, user).with_entities(
            ChatDirectConversation.id, ChatDirectConversation.user_low_id, ChatDirectConversation.user_high_id).all()
        peer_ids = {high if low == user.id else low for _cid, low, high in conversations}
        peers = {uid: (name or login, department) for uid, name, login, department in db.query(
            AppUser.id, AppUser.full_name, AppUser.username, AppUser.department).filter(AppUser.id.in_(peer_ids))} if peer_ids else {}
        for cid, low, high in conversations:
            title, department = peers[high if low == user.id else low]
            rows.append(dict(key=f'direct:{cid}', kind='direct', project_id=cid, title=title, subtitle=department or ''))
    if discussions.schema_ready(db):
        member_ids = {str(uid) for uid, in db.query(DiscussionMember.room_id).filter_by(user_id=user.id)}
        rooms = discussions.visible_room_specs(db, user, [row for row in discussions.room_specs(db) if row['id'] in member_ids])
        for room in rooms:
            rows.append(dict(key=f"discussion:{room['id']}", kind='discussion', project_id=UUID(room['id']),
                             title=room['name'], subtitle='讨论群', deletion_protected=room.get('deletion_protected', False)))

    words = keyword.casefold().split()
    filtered = [row for row in rows if all(word in f"{row['title']} {row['subtitle'] or ''}".casefold() for word in words)]
    filtered.sort(key=lambda row: (row['title'].casefold(), row['key']))
    page = filtered[offset:offset + limit]
    # 只对这一页计算人数和分类，默认目录仍负责完整未读提醒。
    decorate_member_counts(db, page)
    categories.decorate_sessions(db, page)
    return dict(items=page, total=len(filtered), offset=offset, limit=limit,
                has_more=offset + len(page) < len(filtered))
