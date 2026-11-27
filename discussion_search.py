"""讨论消息搜索共用条件：所有类型、发送人、日期与关键词使用 AND 组合。"""
from datetime import datetime, time, timedelta
from sqlalchemy import String, and_, cast, false, func, inspect, literal, or_
from fastapi import HTTPException
from chat_time import BUSINESS_TIMEZONE
from search_matching import keyword_contains, search_terms
from models import ChatProjectAttachment as Attachment

KINDS = {'all', 'file', 'media', 'link', 'miniapp'}


def apply_filters(db, query, message, room_id, *, keyword='', kind='all', sender_user_id=None,
                  start_date=None, end_date=None, format_filters=''):
    if format_filters:
        from chat_text_format import format_condition
        from discussion_chat_models import DiscussionMessageFormat as Format
        condition=format_condition(db,Format.content_json,format_filters)
        if not inspect(db.connection()).has_table(Format.__tablename__):return query.filter(false())
        query=query.filter(message.recalled_at.is_(None),db.query(Format.message_id).filter(Format.message_id==message.id,condition).exists())
    if kind not in KINDS:
        raise HTTPException(422, '不支持的消息类型')
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, '开始日期不能晚于结束日期')
    if keyword.strip() or kind != 'all' or sender_user_id or start_date or end_date:
        query = query.filter(message.recalled_at.is_(None))
    if sender_user_id:
        query = query.filter(message.sender_id == sender_user_id)
    if start_date:
        query = query.filter(message.created_at >= datetime.combine(start_date, time.min, BUSINESS_TIMEZONE))
    if end_date:
        query = query.filter(message.created_at < datetime.combine(end_date + timedelta(days=1), time.min, BUSINESS_TIMEZONE))

    attachment_ready = (bool(keyword.strip()) or kind in {'file', 'media'}) and inspect(db.connection()).has_table(Attachment.__tablename__)
    def attachment_matches(*conditions):
        if not attachment_ready:
            return false()
        # SQLite 的 UUID 转字符串不带横线；两侧统一后仍精确匹配完整引用。
        reference = literal('[附件](discussionfile://') + func.replace(cast(Attachment.id, String), '-', '') + literal(')')
        return db.query(Attachment.id).filter(
            Attachment.storage_name.startswith(f'discussion_{room_id.hex}_', autoescape=True),
            func.replace(func.lower(message.content), '-', '').contains(reference), *conditions).exists()

    image = Attachment.content_type.ilike('image/%')
    video = Attachment.content_type.ilike('video/%')
    if kind == 'file':
        query = query.filter(attachment_matches(~image, ~video))
    elif kind == 'media':
        query = query.filter(or_(attachment_matches(or_(image, video)),
            message.content.contains('![截图](screenshot://')))
    elif kind == 'link':
        query = query.filter(or_(*(message.content.ilike(f'%{prefix}%') for prefix in ('https://', 'http://', 'www.'))))
    elif kind == 'miniapp':
        query = query.filter(or_(*(message.content.contains(marker) for marker in (
            '#小程序://', 'weixin://dl/business/', 'https://wxaurl.cn/', 'https://wxmpurl.cn/'))))
    for term in search_terms(keyword):
        query = query.filter(or_(keyword_contains(message.content, term), keyword_contains(message.sender_name, term),
            attachment_matches(keyword_contains(Attachment.original_name, term))))
    return query


def sender_options(db, user, room_id):
    from discussion_chat_service import require_room, Message
    require_room(db, user, room_id)
    rows = db.query(Message.sender_id, Message.sender_name, func.max(Message.id).label('latest')).filter(
        Message.room_id == room_id, Message.recalled_at.is_(None)).group_by(Message.sender_id, Message.sender_name)
    senders = {}
    for uid, name, _latest in rows.order_by(func.max(Message.id).desc(), Message.sender_id):
        senders.setdefault(str(uid), dict(id=str(uid), name=name))
    return dict(senders=list(senders.values()))
