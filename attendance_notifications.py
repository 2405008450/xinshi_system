"""请假、业务铃铛及私聊消息在同一事务落库，提交后才推送。"""
from uuid import uuid4
from sqlalchemy import func,or_
from sqlalchemy.dialects.postgresql import insert
from models import AppUser,AppNotification,ChatDirectConversation,ChatDirectMember,ChatProjectMessage
from chat_time import now

def queue_leave_notifications(db,user,leave,minutes):
    moment=now();local=moment.replace(tzinfo=None)
    title=f'请假通知 · {user.full_name or user.username}'
    content=f'{user.full_name or user.username} 请假：{leave.start_at.strftime("%Y年%m月%d日 %H:%M")} 至 {leave.end_at.strftime("%Y年%m月%d日 %H:%M")}（UTC+8），班次内 {minutes:g} 分钟（已扣除午休及班间休息）。原因：{leave.reason}'
    return queue_attendance_notifications(db,user,leave.id,title,content,'attendance_leave')


def queue_attendance_notifications(db,user,entity_id,title,content,notification_type):
    moment=now();local=moment.replace(tzinfo=None)
    events=[]
    recipients=db.query(AppUser).filter(AppUser.is_active.is_(True),AppUser.is_deleted.is_(False)).all()
    others=[target for target in recipients if target.id!=user.id]
    postgres=db.get_bind().dialect.name=='postgresql'
    if postgres and others:
        pairs=[dict(id=uuid4(),user_low_id=min(user.id,target.id),user_high_id=max(user.id,target.id),created_at=moment) for target in others]
        db.execute(insert(ChatDirectConversation).values(pairs).on_conflict_do_nothing())
    conversations=db.query(ChatDirectConversation).filter(or_(ChatDirectConversation.user_low_id==user.id,ChatDirectConversation.user_high_id==user.id)).order_by(ChatDirectConversation.id).with_for_update().all()
    by_target={(row.user_high_id if row.user_low_id==user.id else row.user_low_id):row for row in conversations}
    memberships=[]
    sequence=(db.query(func.max(ChatProjectMessage.sequence_no)).scalar() or 0) if not postgres else 0
    for target in recipients:
        notification=AppNotification(id=uuid4(),recipient_user_id=target.id,title=title,content=content,notification_type=notification_type,related_entity_id=entity_id,is_read=False,created_at=local)
        db.add(notification);events.append((target.id,{'type':'notification','notification':{'id':str(notification.id),'recipient_user_id':str(target.id),'title':title,'content':content,'notification_type':notification_type,'is_read':False,'created_at':moment.isoformat(),'related_entity_id':str(entity_id)}}))
        if target.id==user.id:continue
        low,high=sorted((user.id,target.id))
        conversation=by_target.get(target.id)
        if not conversation:
            conversation=ChatDirectConversation(id=uuid4(),user_low_id=low,user_high_id=high,created_at=moment);db.add(conversation)
        for uid in (low,high):
            memberships.append(dict(conversation_id=conversation.id,user_id=uid,last_read_sequence=0,pinned=False,starred=False,muted=False))
        message=ChatProjectMessage(id=uuid4(),direct_conversation_id=conversation.id,sender_user_id=user.id,sender_name=user.full_name or user.username,content=content,message_type=notification_type,event_data={('leave_id' if notification_type=='attendance_leave' else 'request_id'):str(entity_id)},created_at=local,updated_at=local)
        if not postgres:sequence+=1;message.sequence_no=sequence
        db.add(message);conversation.last_message_at=moment
        db.add(AppNotification(id=uuid4(),recipient_user_id=target.id,title=title,content=content,notification_type='direct_chat',related_entity_id=conversation.id,related_project_type='direct',is_read=False,created_at=local))
        event={'type':'direct_chat_changed','projectId':str(conversation.id),'kind':'message','messageId':str(message.id)}
        events.extend([(target.id,event),(user.id,event)])
    if postgres and memberships:
        db.execute(insert(ChatDirectMember).values(memberships).on_conflict_do_update(index_elements=['conversation_id','user_id'],set_={'hidden_at':None}))
    else:
        for values in memberships:
            member=db.get(ChatDirectMember,(values['conversation_id'],values['user_id']))
            if member:member.hidden_at=None
            else:db.add(ChatDirectMember(**values))
    db.flush()
    return events

def publish_leave_notifications(events):
    import logging
    from notification_ws import dispatch_personal_message
    for uid,event in events:
        try:dispatch_personal_message(uid,event)
        except Exception:logging.getLogger(__name__).warning('leave_realtime_delivery_deferred')
