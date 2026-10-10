"""双方私聊：成员权限、并发幂等和附件隔离。管理员没有旁路访问权限。"""
from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from models import (AppUser, ChatDirectConversation, ChatDirectMember, ChatProjectMessage,
                    ChatProjectAttachment, ChatProjectMessageAttachment, ChatProjectMessageFavorite,
                    ChatProjectMessageAcknowledgement)
from notification_ws import broadcast_to_users
from chat_time import now, api_time
import annotation_chat_service as group_service


def require_project(db, project_id, user, *, lock=False):
    query = db.query(ChatDirectConversation).filter(ChatDirectConversation.id == project_id)
    conversation = (query.with_for_update() if lock else query).first()
    if not user.is_active or not conversation or user.id not in (conversation.user_low_id, conversation.user_high_id):
        raise HTTPException(404, '会话不存在或不可访问')
    return conversation


def open_conversation(db, user, target_id):
    target = db.get(AppUser, target_id)
    if not user.is_active or not target or not target.is_active or target_id == user.id:
        raise HTTPException(400, '请选择其他启用的内部用户')
    low, high = sorted((user.id, target_id))
    db.execute(insert(ChatDirectConversation).values(user_low_id=low, user_high_id=high).on_conflict_do_nothing())
    conversation = db.query(ChatDirectConversation).filter_by(user_low_id=low, user_high_id=high).with_for_update().one()
    for uid in (low, high):
        db.execute(insert(ChatDirectMember).values(conversation_id=conversation.id, user_id=uid).on_conflict_do_nothing())
    db.get(ChatDirectMember, (conversation.id, user.id), populate_existing=True).hidden_at = None
    db.commit()
    publish(db, conversation.id, 'state')
    return {'id': conversation.id, 'title': target.full_name or target.username, 'subtitle': '内部私聊'}


def message_query(db, project_id):
    return db.query(ChatProjectMessage).options(selectinload(ChatProjectMessage.mentions),
        selectinload(ChatProjectMessage.acknowledgements),
        selectinload(ChatProjectMessage.attachment_links).selectinload(ChatProjectMessageAttachment.attachment)
    ).filter(ChatProjectMessage.direct_conversation_id == project_id)


def publish(db, project_id, kind='changed', message_id=None):
    row = db.get(ChatDirectConversation, project_id)
    ids = [uid for uid in (row.user_low_id, row.user_high_id) if db.get(AppUser, uid).is_active]
    broadcast_to_users(ids, {'type': 'direct_chat_changed', 'projectId': str(project_id),
        'kind': kind, 'messageId': str(message_id) if message_id else None})


def serialize_many(db, rows, user):
    from routers.project_chat import _serialize_message
    from project_chat_crud import get_chat_message_favorite_times
    favorites = get_chat_message_favorite_times(db, [row.id for row in rows], user.id)
    reply_ids = {row.reply_to_message_id for row in rows if row.reply_to_message_id}
    replies = {row.id: row for row in db.query(ChatProjectMessage).filter(ChatProjectMessage.id.in_(reply_ids)).all()} if reply_ids else {}
    result = []
    for row in rows:
        data = _serialize_message(row, 'direct', favorites.get(row.id), user.id).model_dump()
        data.update(sequence_no=row.sequence_no, client_message_id=row.client_message_id,
            recalled_at=row.recalled_at, recall_label=row.recall_label,
            can_recall=group_service.can_recall(row, user.id), reply=None)
        reply = replies.get(row.reply_to_message_id)
        if reply and reply.direct_conversation_id == row.direct_conversation_id:
            data['reply'] = {'id': reply.id, 'sender_name': reply.sender_name,
                'content': reply.recall_label if reply.recalled_at else reply.content[:200] or '[附件]', 'recalled': bool(reply.recalled_at)}
        if row.recalled_at:
            data.update(content='', attachments=[], mentions=[], reply=None, content_json=None,
                acknowledgements=[], acknowledgement_count=0, is_acknowledged=False, is_favorited=False, favorited_at=None)
        result.append(api_time(data))
    return result


def send_message(db, project_id, user, payload):
    conversation = require_project(db, project_id, user, lock=True)
    other_id = conversation.user_high_id if user.id == conversation.user_low_id else conversation.user_low_id
    if not db.get(AppUser, other_id).is_active:
        raise HTTPException(400, '对方账号已停用')
    if payload.mentioned_user_ids or payload.mentioned_user_id:
        raise HTTPException(400, '私聊不支持提及')
    if payload.client_message_id:
        existing = message_query(db, project_id).filter_by(sender_user_id=user.id, client_message_id=payload.client_message_id).first()
        if existing:
            return existing
    if payload.reply_to_message_id:
        reply = message_query(db, project_id).filter_by(id=payload.reply_to_message_id).first()
        if not reply or reply.recalled_at:
            raise HTTPException(400, '引用消息不存在、已撤回或属于其他会话')
    ids = set(payload.attachment_ids)
    attachments = db.query(ChatProjectAttachment).filter(ChatProjectAttachment.id.in_(ids)).with_for_update().all() if ids else []
    if len(attachments) != len(ids) or any(a.uploaded_by != user.id or a.direct_conversation_id != project_id for a in attachments):
        raise HTTPException(400, '附件不属于当前用户或会话')
    if ids and db.query(ChatProjectMessageAttachment).filter(ChatProjectMessageAttachment.attachment_id.in_(ids)).first():
        raise HTTPException(400, '附件已经发送，请重新上传')
    stamp = now()
    message = ChatProjectMessage(direct_conversation_id=project_id, sender_user_id=user.id,
        sender_name=user.full_name or user.username, content=payload.content.strip(), message_type='user',
        created_at=stamp.replace(tzinfo=None), updated_at=stamp.replace(tzinfo=None),
        client_message_id=payload.client_message_id, reply_to_message_id=payload.reply_to_message_id, event_data={})
    db.add(message); db.flush()
    db.add_all(ChatProjectMessageAttachment(message_id=message.id, attachment_id=a.id) for a in attachments)
    conversation.last_message_at = stamp
    for member in db.query(ChatDirectMember).filter_by(conversation_id=project_id):
        member.hidden_at = None
    db.commit()
    publish(db, project_id, 'message', message.id)
    return message_query(db, project_id).filter_by(id=message.id).one()


def recall_message(db, project_id, message_id, user):
    require_project(db, project_id, user, lock=True)
    message = message_query(db, project_id).filter_by(id=message_id).first()
    if not message:
        raise HTTPException(404, '消息不存在')
    if message.sender_user_id != user.id:
        raise HTTPException(403, '不能撤回他人的消息')
    if message.recalled_at:
        return message
    if not group_service.can_recall(message, user.id):
        raise HTTPException(403, '只能撤回本人24小时内的消息')
    message.recalled_at = now().replace(tzinfo=None)
    message.recalled_by = user.id
    message.recall_label = f'{message.sender_name}撤回了一条消息'
    message.content = ''; message.content_json = None; message.updated_at = message.recalled_at
    db.query(ChatProjectMessageFavorite).filter_by(message_id=message.id).delete(synchronize_session=False)
    db.query(ChatProjectMessageAcknowledgement).filter_by(message_id=message.id).delete(synchronize_session=False)
    db.commit(); publish(db, project_id, 'recall', message.id)
    return message


def authorize_attachment(db, attachment_id, user):
    attachment = db.get(ChatProjectAttachment, attachment_id)
    if not attachment or not attachment.direct_conversation_id:
        raise HTTPException(404, '附件不存在')
    require_project(db, attachment.direct_conversation_id, user)
    links = db.query(ChatProjectMessage).join(ChatProjectMessageAttachment,
        ChatProjectMessageAttachment.message_id == ChatProjectMessage.id).filter(ChatProjectMessageAttachment.attachment_id == attachment_id).all()
    if (not links and attachment.uploaded_by != user.id) or (links and not any(not m.recalled_at for m in links)):
        raise HTTPException(404, '附件未发送或已撤回')
    return attachment
