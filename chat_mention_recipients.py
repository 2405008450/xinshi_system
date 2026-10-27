"""@所有人仅展开当前会话的有效成员；不隐式扩大访问范围。"""
from fastapi import HTTPException
from models import AppUser, ChatDirectMember
from chat_access_service import member_ids


def resolve_mentions(db, kind, conversation_id, sender, explicit=(), mention_all=False):
    members = ({uid for uid, in db.query(ChatDirectMember.user_id).filter_by(conversation_id=conversation_id)}
               if kind == 'direct' else member_ids(db, kind, conversation_id))
    requested = set(explicit or ()) - {sender.id}
    if kind in ('discussion', 'direct') and not requested.issubset(members):
        raise HTTPException(422, '只能提及当前会话成员')
    if mention_all:
        requested |= members - {sender.id}
    users = db.query(AppUser).filter(AppUser.id.in_(requested), AppUser.is_active.is_(True)).all() if requested else []
    if mention_all and kind in ('annotation','translation'):
        import annotation_chat_service as annotation
        users=[user for user in users if annotation.can_view(db,user)]
    active_ids = {user.id for user in users}
    if not (set(explicit or ()) - {sender.id}).issubset(active_ids):
        raise HTTPException(422, '被提及用户不存在或已停用')
    return sorted(active_ids, key=str)
