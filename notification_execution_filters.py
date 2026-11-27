"""从关联业务读取发送人与当前执行状态；不将已读状态冒充执行状态。"""
from sqlalchemy import String, cast, and_, case, func, inspect, literal, or_, select
from sqlalchemy.orm import aliased
from models import AppUser


def expressions(db, notice):
    from resource_request_dispatch_models import ResourceRequestDispatch as Batch, ResourceRequestDispatchRecipient as Recipient
    from resource_issue_models import DevelopmentIssue, DevelopmentIssueTask
    from meeting_models import Meeting, MeetingActionTask
    available=set(inspect(db.get_bind()).get_table_names())
    sender_cases=[]; state_cases=[]
    # 回执通知在标题明确保存发送人；只在姓名唯一时解析，避免同名误归属。
    person=aliased(AppUser)
    name=func.coalesce(func.nullif(person.full_name,''),person.username)
    explicit=or_(func.substr(notice.title,1,func.length(name)+3)==name+' · ',
        func.substr(notice.content,1,func.length(name)+len(' 向你发起了 '))==name+' 向你发起了 ',
        func.substr(notice.content,1,func.length(name)+len('安排：'))==name+'安排：')
    actor_count=select(func.count()).select_from(person).where(explicit).correlate(notice).scalar_subquery()
    actor=select(person.id).where(explicit).order_by(person.id).limit(1).correlate(notice).scalar_subquery()
    if Batch.__tablename__ in available and Recipient.__tablename__ in available:
        batch_sender=select(Batch.sender_id).where(Batch.id==notice.related_entity_id).correlate(notice).scalar_subquery()
        is_receipt=or_(notice.title.contains(' · 已收到 · '),notice.title.contains(' · 已执行 · '),notice.title.contains(' · 确认收到取消通知 · '))
        sender_cases.append((notice.notification_type=='resource_request_dispatch',case((is_receipt,case((actor_count==1,actor),else_=None)),else_=batch_sender)))
        scope=and_(Recipient.dispatch_id==notice.related_entity_id,or_(Recipient.user_id==notice.recipient_user_id,batch_sender==notice.recipient_user_id))
        total=select(func.count()).select_from(Recipient).where(scope).correlate(notice).scalar_subquery()
        done=select(func.count()).select_from(Recipient).where(scope,Recipient.processed_at.is_not(None)).correlate(notice).scalar_subquery()
        received=select(func.count()).select_from(Recipient).where(scope,Recipient.received_at.is_not(None)).correlate(notice).scalar_subquery()
        cancelled=or_(select(Batch.kind).where(Batch.id==notice.related_entity_id).correlate(notice).scalar_subquery()=='cancellation',
            select(Batch.id).where(Batch.kind=='cancellation',func.replace(Batch.idempotency_key,'-','')=='canceldispatch:'+func.replace(cast(notice.related_entity_id,String),'-','')).correlate(notice).exists())
        state_cases.append((notice.notification_type=='resource_request_dispatch',case((cancelled,'cancelled'),(total==0,'not_applicable'),(done==total,'completed'),(done>0,'in_progress'),(received>0,'received'),else_='pending')))
    if DevelopmentIssue.__tablename__ in available:
        sender_cases.append((notice.notification_type=='chat_summary',select(DevelopmentIssue.collected_by).where(DevelopmentIssue.id==notice.related_entity_id).correlate(notice).scalar_subquery()))
        if DevelopmentIssueTask.__tablename__ in available:
            scope=and_(DevelopmentIssueTask.issue_id==notice.related_entity_id,DevelopmentIssueTask.executor_id==notice.recipient_user_id)
            count=select(func.count()).select_from(DevelopmentIssueTask).where(scope).correlate(notice).scalar_subquery()
            def has(status):return select(DevelopmentIssueTask.id).where(scope,DevelopmentIssueTask.status==status).correlate(notice).exists()
            state_cases.append((notice.notification_type=='chat_summary',case((count==0,'not_applicable'),(has('in_progress'),'in_progress'),(has('pending'),'pending'),(has('completed'),'completed'),else_='cancelled')))
    if Meeting.__tablename__ in available:
        sender_cases.append((notice.notification_type=='meeting_invitation',select(Meeting.organizer_id).where(Meeting.id==notice.related_entity_id).correlate(notice).scalar_subquery()))
        lifecycle=select(func.coalesce(Meeting.association['lifecycle']['status'].as_string(),'pending')).where(Meeting.id==notice.related_entity_id).correlate(notice).scalar_subquery()
        state_cases.append((notice.notification_type=='meeting_invitation',case((lifecycle=='ended','completed'),(lifecycle=='cancelled','cancelled'),(lifecycle=='in_progress','in_progress'),(lifecycle=='pending','pending'),else_='not_applicable')))
    if MeetingActionTask.__tablename__ in available:
        scope=and_(MeetingActionTask.meeting_id==notice.related_entity_id,MeetingActionTask.assignee_id==notice.recipient_user_id)
        sender_cases.append((notice.notification_type=='meeting_task',select(MeetingActionTask.arranger_id).where(scope).order_by(MeetingActionTask.assigned_at.desc(),MeetingActionTask.id).limit(1).correlate(notice).scalar_subquery()))
        def has_task(status):return select(MeetingActionTask.id).where(scope,MeetingActionTask.status==status).correlate(notice).exists()
        state_cases.append((notice.notification_type=='meeting_task',case((has_task('in_progress'),'in_progress'),(has_task('pending'),'pending'),(has_task('completed'),'completed'),else_='not_applicable')))
    sender=case(*sender_cases,else_=case((actor_count==1,actor),else_=None))
    state=case(*state_cases,else_='not_applicable') if state_cases else literal('not_applicable')
    return sender,state
