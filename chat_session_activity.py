"""默认目录只加载近期或待处理会话；权限边界仍由调用方的目录查询决定。"""
from datetime import timedelta

from sqlalchemy import and_, func, or_, select

from business_time import business_now
from chat_receipt_read import received
from models import ChatProjectMessage


def active_project_scope(db, message_column, scope_column, baseline_column, user_id,
                         *, pinned=None, starred=None):
    message = ChatProjectMessage
    cutoff = business_now() - timedelta(days=30)
    activity = select(message.id).where(
        message_column == scope_column,
        message.message_type == 'user',
        or_(message.created_at >= cutoff, and_(
            message.sequence_no > func.coalesce(baseline_column, 0),
            message.sender_user_id != user_id,
            message.recalled_at.is_(None),
            ~received(db, message, user_id),
        )),
    ).correlate(scope_column.class_, baseline_column.class_).exists()
    return or_(activity, *[flag.is_(True) for flag in (pinned, starred) if flag is not None])


def active_discussion_ids(db, user_id):
    from discussion_chat_models import DiscussionMember, DiscussionMessage
    message = DiscussionMessage
    member = DiscussionMember
    # 沿用讨论目录的未读口径，历史会话一旦收到新消息即回到默认目录。
    return {str(uid) for uid, in db.query(message.room_id).join(
        member, and_(member.room_id == message.room_id, member.user_id == user_id),
    ).filter(or_(
        message.created_at >= business_now() - timedelta(days=30),
        and_(message.id > func.coalesce(member.last_read_id, 0),
             message.sender_id != user_id, message.recalled_at.is_(None)),
    )).distinct()}
