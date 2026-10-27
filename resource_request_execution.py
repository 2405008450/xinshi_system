"""发帖接收人的渠道选择与不可变执行回执。"""
from uuid import UUID
from pydantic import BaseModel,Field
from fastapi import HTTPException
from models import AppUser
from resource_development_models import DevelopmentOption as Option,DevelopmentChannelMember as Member
from resource_request_dispatch_models import ResourceRequestDispatch as Batch,ResourceRequestDispatchRecipient as Recipient,ResourceRequestExecutionReply as Reply
from resource_channel_service import CHANNEL_KINDS,serialize_channels
from resource_request_send_history import stamp

class ExecutionWrite(BaseModel):
    platform_ids:list[UUID]=Field(min_length=1,max_length=100)
    content:str=Field(default='',max_length=5000)
    idempotency_key:str=Field(min_length=16,max_length=128)

def access(db,user,batch_id,recipient_only=False):
    batch=db.get(Batch,batch_id)
    recipient=db.query(Recipient).filter_by(dispatch_id=batch_id,user_id=user.id).with_for_update().first() if recipient_only else db.get(Recipient,(batch_id,user.id))
    if not batch or batch.kind!='post' or (not recipient and (recipient_only or batch.sender_id!=user.id)):
        raise HTTPException(404,'发帖需求通知不存在')
    return batch,recipient

def matched(db,user):
    return db.query(Option).join(Member,Member.platform_id==Option.id).filter(Option.kind.in_(CHANNEL_KINDS),Member.user_id==user.id,Member.role=='user').order_by(Option.name,Option.id).all()

def channels(db,user,batch_id):
    access(db,user,batch_id,True)
    from permission_service import user_has_permission
    allowed=any(user_has_permission(db,user.id,p) for p in ['talents:write','translators:write','resource_development:delegate'])
    from resource_channel_service import hierarchy_available
    return dict(items=serialize_channels(db,matched(db,user)),can_manage=allowed,user_id=str(user.id),hierarchy_available=hierarchy_available(db))

def replies(db,batch_ids):
    if not batch_ids:return []
    people={p.id:p.full_name or p.username for p in db.query(AppUser).join(Reply,Reply.user_id==AppUser.id).filter(Reply.dispatch_id.in_(batch_ids))}
    return [dict(id=str(r.id),dispatch_id=str(r.dispatch_id),user_id=str(r.user_id),name=people.get(r.user_id,'历史人员'),platforms=r.platforms,content=r.content,created_at=stamp(r.created_at)) for r in db.query(Reply).filter(Reply.dispatch_id.in_(batch_ids)).order_by(Reply.created_at.desc(),Reply.id.desc())]

def send(db,user,batch_id,payload):
    from resource_request_cancellation import lock_request, assert_active
    candidate=db.get(Batch,batch_id)
    if candidate:lock_request(db,candidate.request_id)
    batch,recipient=access(db,user,batch_id,True)
    assert_active(db,batch)
    ids=set(payload.platform_ids)
    old=db.query(Reply).filter_by(idempotency_key=payload.idempotency_key).first()
    if old:
        if old.dispatch_id!=batch_id or old.user_id!=user.id or {p['id'] for p in old.platforms}!={str(i) for i in ids} or old.content!=payload.content.strip():
            raise HTTPException(409,'回复标识已用于其他操作，请重新回复')
        from resource_request_dispatch import detail
        return detail(db,user,batch_id)
    rows={p.id:p for p in matched(db,user)}
    if not ids<=rows.keys():raise HTTPException(422,'所选平台已删除或不再由你使用，请刷新后重新选择')
    if not recipient.received_at:raise HTTPException(409,'请先确认已收到，再提交执行回执')
    if not payload.content.strip():raise HTTPException(422,'请填写具体处理／发布情况')
    from resource_channel_models import ChannelAccountLink
    parents={a:parent for a,parent in db.query(ChannelAccountLink.account_id,Option.name).join(Option,Option.id==ChannelAccountLink.parent_id).filter(ChannelAccountLink.account_id.in_(ids))}
    platforms=[dict(id=str(uid),name=rows[uid].name,parent_name=parents.get(uid)) for uid in sorted(ids,key=str)]
    db.add(Reply(dispatch_id=batch_id,user_id=user.id,platforms=platforms,content=payload.content.strip(),idempotency_key=payload.idempotency_key))
    from chat_time import now
    if not recipient.processed_at:recipient.processed_at=now()
    from resource_request_dispatch import publish,commit,detail
    publish(db,[batch.sender_id],f'{user.full_name or user.username} · 执行回执 · '+ '、'.join(p['name'] for p in platforms),batch)
    commit(db)
    return detail(db,user,batch_id)
