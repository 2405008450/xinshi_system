"""笔译项目发送到按业务日期归档的全员会话；独立幂等发送记录。"""
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from weakref import WeakKeyDictionary
from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid, inspect, func
from sqlalchemy.orm import mapped_column
from fastapi import HTTPException
from models import Base, AppUser, TranslationProject
from annotation_progress_time import business_now

ROOT='dcb1f917-6000-4000-8000-000000000003'


class TranslationChatConfig(Base):
    __tablename__='translation_chat_config'
    id=mapped_column(Integer,primary_key=True)
    settings=mapped_column(JSON,nullable=False)
    revision=mapped_column(Integer,nullable=False,default=1)
    updated_by=mapped_column(Uuid,ForeignKey('app_user.id'))
    updated_at=mapped_column(DateTime(timezone=True),nullable=False,default=business_now)


class TranslationProjectConversation(Base):
    __tablename__='translation_project_conversation'
    project_id=mapped_column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'),primary_key=True)
    day=mapped_column(Date,primary_key=True)
    room_id=mapped_column(Uuid,ForeignKey('chat_session_category.id'),nullable=False,unique=True)
    folder_id=mapped_column(Uuid,ForeignKey('chat_session_category.id'),nullable=False)
    title=mapped_column(Text,nullable=False)


class TranslationChatDispatch(Base):
    __tablename__='translation_chat_dispatch'
    id=mapped_column(Uuid,primary_key=True,default=uuid4)
    request_key=mapped_column(Uuid,nullable=False,unique=True)
    project_id=mapped_column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'),nullable=False,index=True)
    room_id=mapped_column(Uuid,nullable=False)
    actor_id=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    message_ids=mapped_column(JSON,nullable=False)
    snapshot=mapped_column(JSON,nullable=False)
    created_at=mapped_column(DateTime(timezone=True),nullable=False,default=business_now)


class TranslationMailChatIntent(Base):
    __tablename__='translation_mail_chat_intent'
    mail_id=mapped_column(Uuid,ForeignKey('business_mail.id',ondelete='CASCADE'),primary_key=True)
    audience=mapped_column(JSON,nullable=False,default=list)
    error=mapped_column(Text)


TABLES=(TranslationChatConfig,TranslationProjectConversation,TranslationChatDispatch,TranslationMailChatIntent)
_READY=WeakKeyDictionary()


def ready(db):
    bind=db.get_bind()
    if db.info.get('_translation_chat_ready') or _READY.get(bind):return True
    result=all(inspect(db.connection()).has_table(model.__tablename__) for model in TABLES)
    if result:
        db.info['_translation_chat_ready']=True
        _READY[bind]=True
    return result


def require_ready(db):
    if not ready(db):raise HTTPException(503,'笔译项目会话发送表尚未初始化')


def people(db):
    return db.query(AppUser).filter(AppUser.is_active.is_(True),AppUser.is_deleted.is_(False)).order_by(AppUser.username).all()


def defaults(db):
    users={row.username.casefold():str(row.id) for row in people(db)}
    return {'weekday_user_id':users.get('shaofei'),'leave_backup_user_id':users.get('thomas'),
            'sunday_user_ids':[users[name] for name in ('menghua','lixian') if name in users], 'extra_audience':[], 'participant_audience':['all']}


def settings(db):
    row=db.get(TranslationChatConfig,1) if ready(db) else None
    return {**defaults(db),**(row.settings if row else {})},row


def can_manage(db,user):
    from permission_service import user_has_permission
    return user_has_permission(db,user.id,'*') or user_has_permission(db,user.id,'projects:write')


def catalog(db,user):
    from department_models import Department
    config,row=settings(db)
    departments=db.query(Department).all()
    departments.sort(key=lambda item:(0 if item.name=='笔译项目部' else 1,item.name))
    return dict(ready=ready(db),can_manage=can_manage(db,user),revision=row.revision if row else 0,settings=config,
        users=[{'id':str(row.id),'name':row.full_name or row.username} for row in people(db)],
        audience=[{'value':'all','label':'全体'}]+[{'value':'department:'+str(row.id),'label':row.name} for row in departments]+[{'value':'user:'+str(row.id),'label':row.full_name or row.username} for row in people(db)])


def save_settings(db,user,payload):
    require_ready(db)
    if not can_manage(db,user):raise HTTPException(403,'没有修改笔译项目会话设置的权限')
    db.query(AppUser).filter_by(id=user.id).with_for_update().one()
    row=db.get(TranslationChatConfig,1)
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'设置已被修改，请重新打开')
    config=payload.model_dump(exclude={'revision'},mode='json')
    valid={str(person.id) for person in people(db)}
    selected={config['weekday_user_id'],config['leave_backup_user_id'],*config['sunday_user_ids']}-{None}
    if not selected.issubset(valid):raise HTTPException(422,'所选人员已停用或不存在')
    resolve_audience(db,config['extra_audience'],valid)
    resolve_audience(db,config['participant_audience'],valid)
    if row is None:row=TranslationChatConfig(id=1,revision=0);db.add(row)
    row.settings=config;row.revision+=1;row.updated_by=user.id;row.updated_at=business_now()
    db.commit();return catalog(db,user)


def resolve_audience(db,selections,valid):
    from department_models import Department,DepartmentMember
    result=set()
    for selection in selections:
        if selection=='all':result.update(valid);continue
        kind,_,key=selection.partition(':')
        try:identifier=UUID(key)
        except ValueError:raise HTTPException(422,'无效的补充提醒对象')
        if kind=='user' and key in valid:result.add(key)
        elif kind=='department' and db.get(Department,identifier):
            result.update(str(uid) for uid, in db.query(DepartmentMember.user_id).filter_by(department_id=identifier) if str(uid) in valid)
        else:raise HTTPException(422,'补充提醒对象不存在或已停用')
    return result


def recipients(db,config,at,extra=()):
    users={str(row.id):row for row in people(db)}
    valid=set(users);selected=set();warnings=[]
    from leave_service import get_active_leave
    if at.weekday()<6:
        identifier=config.get('weekday_user_id')
        if identifier in users and get_active_leave(db,UUID(identifier),at):identifier=config.get('leave_backup_user_id')
        if identifier in users and not get_active_leave(db,UUID(identifier),at):selected.add(identifier)
        else:warnings.append('工作日默认提醒人或请假替补不可用，请补选提醒对象')
    else:
        from weekend_duty_management import WeekendDutyPublication
        from weekend_duty import WeekendDutyPlan
        inspector=inspect(db.connection());month=at.date().replace(day=1)
        plan=db.get(WeekendDutyPublication,month) if inspector.has_table(WeekendDutyPublication.__tablename__) else None
        if plan is None and inspector.has_table(WeekendDutyPlan.__tablename__):plan=db.get(WeekendDutyPlan,month)
        on_duty={entry['user_id'] for entry in (plan.assignments if plan else []) if entry.get('date')==at.date().isoformat()}
        selected.update(uid for uid in config.get('sunday_user_ids',[]) if uid in on_duty and uid in valid and not get_active_leave(db,UUID(uid),at))
        if not selected:warnings.append('当日没有匹配的已发布周日值班安排，请补选提醒对象')
    selected.update(resolve_audience(db,[*config.get('extra_audience',[]),*extra],valid))
    return [users[uid] for uid in sorted(selected)],warnings


def aliases(db):
    if not ready(db):return {}
    result={}
    for row in db.query(TranslationProjectConversation):
        result[str(row.room_id)]=row.title
        result[str(row.folder_id)]=row.day.strftime('%y%m%d')
    return result


def counts(db,project_id):
    from business_mail_models import BusinessMail
    return {'mail_count':db.query(func.count(BusinessMail.id)).filter_by(translation_project_id=project_id,status='sent').scalar() or 0,
            'chat_count':db.query(func.count(TranslationChatDispatch.id)).filter_by(project_id=project_id).scalar() or 0 if ready(db) else 0}


def send(db,actor,project_id,request_key,extra=(),mail_id=None):
    require_ready(db)
    project=db.query(TranslationProject).filter_by(id=project_id).with_for_update().first()
    if not project:raise HTTPException(404,'笔译项目不存在')
    prior=db.query(TranslationChatDispatch).filter_by(request_key=request_key).first()
    if prior:
        if prior.project_id!=project_id or prior.actor_id!=actor.id:raise HTTPException(409,'发送请求标识已用于其他操作')
        return {**counts(db,project_id),'room_id':str(prior.room_id),'warnings':prior.snapshot.get('warnings',[])}
    from translation_project_submission import mail_policy
    _,error=mail_policy(db,project)
    if error:raise HTTPException(422,error)
    from business_mail_service import build_preview
    if mail_id:
        from business_mail_models import BusinessMail
        mail=db.get(BusinessMail,mail_id)
        if not mail or mail.translation_project_id!=project_id or mail.status!='sent':raise HTTPException(422,'关联邮件尚未成功发送或不属于此项目')
        subject,body,body_html=mail.subject,mail.body,mail.body_html
    else:
        preview=build_preview(db,'translation',project_id=project_id,current_user=actor)
        if preview['missing_fields']:raise HTTPException(422,'请先补充母订单必填信息：'+'、'.join(preview['missing_fields']))
        subject,body,body_html=preview['subject'],preview['body'],preview['body_html']
        if preview.get('signature_text'):
            body+='\n\n'+preview['signature_text']
        if preview.get('signature_html'):
            body_html=(body_html or '')+preview['signature_html']
    config,_=settings(db);at=business_now();day=at.date()
    targets,warnings=recipients(db,config,at,extra)
    from chat_session_category_models import ChatSessionCategory as Category,ChatSessionCategoryFolder as Folder
    from discussion_chat_models import DiscussionMember,DiscussionMessage
    from sqlalchemy import text
    if db.get_bind().dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':int(day.strftime('%Y%m%d'))+81000000})
    room=db.get(TranslationProjectConversation,(project_id,day))
    client=project.client
    client_name=(client.client_short_name or client.client_name) if client else '未填写客户'
    title=' · '.join([project.order_no,client_name,project.project_name])
    if room is None:
        folder_id=uuid5(NAMESPACE_URL,'xinshi:translation-date:'+day.isoformat())
        folder=db.get(Category,folder_id)
        if folder is None:
            name=day.strftime('%y%m%d')
            if db.query(Category.id).filter_by(name=name).first():name='笔译项目 · '+name
            folder=Category(id=folder_id,name=name,active=True,revision=1,updated_by=actor.id);db.add(folder);db.flush()
            db.add(Folder(category_id=folder_id,parent_key=ROOT))
        room_id=uuid4();db.add(Category(id=room_id,name=title[:80],active=True,revision=1,updated_by=actor.id));db.flush()
        db.add(Folder(category_id=room_id,parent_key=str(folder_id)))
        room=TranslationProjectConversation(project_id=project_id,day=day,room_id=room_id,folder_id=folder_id,title=title);db.add(room)
    else:room.title=title
    existing={uid for uid, in db.query(DiscussionMember.user_id).filter_by(room_id=room.room_id)}
    all_people=people(db)
    participant_ids=resolve_audience(db,config.get('participant_audience',['all']),{str(person.id) for person in all_people})
    participant_ids.update(str(person.id) for person in [actor,*targets])
    for person in all_people:
        if str(person.id) in participant_ids and person.id not in existing:db.add(DiscussionMember(room_id=room.room_id,user_id=person.id,last_read_id=0,pinned=False,starred=False))
    db.flush()
    content=subject+'\n\n'+body
    # 讨论消息存 Text，完整保存正文，不截断；每次有独立 UUID 幂等键。
    message=DiscussionMessage(room_id=room.room_id,sender_id=actor.id,sender_name=actor.full_name or actor.username,client_message_id=request_key,content=content)
    db.add(message);db.flush()
    from discussion_mentions import create as create_mentions
    all_scope='all' in [*config.get('extra_audience',[]),*extra]
    notifications=create_mentions(db,actor,message,SimpleNamespace(mention_all=all_scope),[person for person in targets if person.id!=actor.id],existing|{UUID(uid) for uid in participant_ids})
    db.add(TranslationChatDispatch(request_key=request_key,project_id=project_id,room_id=room.room_id,actor_id=actor.id,message_ids=[str(message.id)],snapshot={'subject':subject,'body':body,'body_html':body_html,'mentioned_user_ids':[str(person.id) for person in targets],'warnings':warnings}))
    db.commit()
    from project_chat_crud import _push_notifications
    from discussion_chat_service import publish
    # 消息和提醒已落库；瞬时连接推送失败不能误报为未发送、诱发重复消息。
    try:
        _push_notifications(notifications)
        publish(db)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('笔译会话已保存，实时推送暂未完成')
    return {**counts(db,project_id),'room_id':str(room.room_id),'warnings':warnings}


def complete_mail_intent(db,mail,actor):
    if mail.project_type!='translation' or mail.status!='sent' or not ready(db):return
    intent=db.get(TranslationMailChatIntent,mail.id)
    if not intent:return
    try:
        send(db,actor,mail.translation_project_id,uuid5(NAMESPACE_URL,'translation-mail:'+str(mail.id)),intent.audience,mail.id)
        intent=db.get(TranslationMailChatIntent,mail.id);intent.error=None;db.commit()
    except Exception as error:
        db.rollback();intent=db.get(TranslationMailChatIntent,mail.id);intent.error=str(getattr(error,'detail',error))[:2000];db.commit()
