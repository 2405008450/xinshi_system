"""@所有人仅展开当前会话的有效成员；不隐式扩大访问范围。"""
from fastapi import HTTPException
from models import AppUser, ChatDirectMember
from chat_access_service import member_ids


def resolve_mentions(db, kind, conversation_id, sender, explicit=(), mention_all=False):
    requested = set(explicit or ()) - {sender.id}
    if not requested and not mention_all:
        return []
    members = ({uid for uid, in db.query(ChatDirectMember.user_id).filter_by(conversation_id=conversation_id)}
               if kind == 'direct' else member_ids(db, kind, conversation_id))
    if kind == 'direct' and not requested.issubset(members):
        raise HTTPException(422, '只能提及当前会话成员')
    if mention_all:
        requested |= members - {sender.id}
    if kind in ('annotation','translation'):
        from annotation_chat_service import project_chat_eligible_ids
        active_ids = project_chat_eligible_ids(db, requested, allow_annotation_department=True)
    else:
        active_ids = {uid for uid, in db.query(AppUser.id).filter(
            AppUser.id.in_(requested), AppUser.is_active.is_(True),
        )} if requested else set()
    if not (set(explicit or ()) - {sender.id}).issubset(active_ids):
        raise HTTPException(422, '被提及用户不存在或已停用')
    return sorted(active_ids, key=str)
