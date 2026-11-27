"""口译、标注、招聘：按日项目会话和持久化邮件联动，仅显式发送时写入。"""
from types import SimpleNamespace
from chat_catalog_read import catalog_cached
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid, inspect, text
from sqlalchemy.orm import mapped_column
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from models import Base
from database import get_db
from routers.auth import get_current_user, require_any_permission
from annotation_progress_time import business_now

LABELS={'interpretation':'口译','annotation':'标注','recruitment':'招聘'}
ROOTS={'interpretation':'dcb1f917-6000-4000-8000-000000000004','annotation':'dcb1f917-6000-4000-8000-000000000002','recruitment':'dcb1f917-6000-4000-8000-000000000005'}
URGENT='（紧急）项目预告知：'
WARNING=URGENT+'相关资料可能尚未完善，请后续补充确认。'


class ProjectChatDispatch(Base):
    __tablename__='project_chat_dispatch'
    request_key=mapped_column(Uuid,primary_key=True)
    module=mapped_column(String(30),nullable=False)
    project_id=mapped_column(Uuid,nullable=False,index=True)
    room_id=mapped_column(Uuid,ForeignKey('chat_session_category.id'),nullable=False)
    actor_id=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    mail_id=mapped_column(Uuid,ForeignKey('business_mail.id',ondelete='SET NULL'))
    snapshot=mapped_column(JSON,nullable=False)
    created_at=mapped_column(DateTime(timezone=True),nullable=False,default=business_now)


class ProjectMailChatIntent(Base):
    __tablename__='project_mail_chat_intent'
    mail_id=mapped_column(Uuid,ForeignKey('business_mail.id',ondelete='CASCADE'),primary_key=True)
    error=mapped_column(Text)


TABLES=(ProjectChatDispatch,ProjectMailChatIntent)


def ready(db):
    if not hasattr(db,'get_bind') or not hasattr(db,'info'):return False
    if db.info.get('_project_delivery_ready'):return True
    result=all(inspect(db.connection()).has_table(model.__tablename__) for model in TABLES)
    if result:db.info['_project_delivery_ready']=True
    return result


def require_ready(db):
    if not ready(db):raise HTTPException(503,'项目会话发送表尚未初始化')


@catalog_cached
def aliases(db):
    if not ready(db):return {}
    result={}
    for row in db.query(ProjectChatDispatch).order_by(ProjectChatDispatch.created_at):
        result[str(row.room_id)]=row.snapshot['title']
        result[row.snapshot['folder_id']]=row.snapshot['day'].replace('-','')[2:]
    return result


def interpretation_chat_body(body):
    # 标题已包含订单、客户及项目名称；每项只移除首个自动生成行，保留后文人工内容。
    redundant={'项目类型','订单号','项目名称','客户简称','口译类型'}
    result=[]
    for line in body.splitlines(keepends=True):
        label=line.partition('：')[0]
        if label in redundant:
            redundant.remove(label)
            continue
        result.append(line)
    return ''.join(result)


def interpretation_editor_extras(db,project,existing_body=''):
    from interpretation_interpreter_requirements import attach as attach_requirements
    from interpretation_client_selection import attach as attach_selection
    attach_requirements(db,[project]);attach_selection(db,[project])
    from interpretation_interpreter_requirements import requirement_lines
    values={key:getattr(project,key,None) for key in ['interpreter_height_requirement','interpreter_appearance_requirement','interpreter_dress_requirement','interpreter_requirements']}
    existing_labels={line.partition('：')[0] for line in existing_body.splitlines() if '：' in line}
    lines=[line for line in requirement_lines(values) if line.partition('：')[0] not in existing_labels]
    if project.interpreter_assignments:
        lines.append('译员安排：')
        ratings={'very_satisfied':'非常满意','satisfied':'满意','basically_satisfied':'基本满意','dissatisfied':'不满意','very_dissatisfied':'非常不满意'}
        for index,item in enumerate(project.interpreter_assignments,1):
            name=item.translator_name or '未命名译员'
            lines.append(f'译员{index}：{name}'+('（客户选定）' if item.client_selected else ''))
            if item.customer_rating:lines.append('客户评价：'+ratings.get(item.customer_rating,item.customer_rating))
            if item.evaluation_note:lines.append('评价/备注：'+item.evaluation_note)
    if project.social_post_request:lines.extend(['需求发布：',project.social_post_request])
    return '\n'.join(lines)


def send(db,actor,module,project_id,request_key,*,emergency=False,mail_id=None,audience=(),status_change_id=None):
    require_ready(db)
    if module not in LABELS:raise HTTPException(422,'不支持的项目类型')
    from business_mail_service import PROJECT_MODELS, PROJECT_FK_FIELDS, build_preview, _project_source
    from business_mail_models import BusinessMail
    model=PROJECT_MODELS[module]
    project=db.query(model).filter(model.id==project_id).with_for_update().first()
    if not project:raise HTTPException(404,'项目不存在')
    previous=db.get(ProjectChatDispatch,request_key)
    if previous:
        same_mail=mail_id is not None and previous.mail_id==mail_id
        if previous.module!=module or previous.project_id!=project_id or (previous.actor_id!=actor.id and not same_mail):raise HTTPException(409,'发送请求标识已用于其他操作')
        return {'room_id':str(previous.room_id),'sent':True}
    status_only=module=='interpretation' and status_change_id is not None
    if status_only and not mail_id:
        from interpretation_status_notice import content
        subject,body=project.order_no+' · 项目状态更新',content(db,project_id,status_change_id)
    elif mail_id:
        mail=db.get(BusinessMail,mail_id)
        if not mail or mail.project_type!=module or getattr(mail,PROJECT_FK_FIELDS[module])!=project_id or mail.status!='sent':raise HTTPException(422,'关联邮件未发送成功或不属于此项目')
        subject,body=mail.subject,mail.body
    else:
        preview=build_preview(db,module,project_id=project_id,current_user=actor,emergency_notice=emergency,
                              source={'manager_contact':None})
        if preview['missing_fields']:raise HTTPException(422,'请先填写项目核心信息：'+'、'.join(preview['missing_fields']))
        subject,body=preview['subject'],preview['body']
    # 团队会话包含非客户/行政部门；生成内容中的客户联系方式不带入会话。
    contact=str(_project_source(module,project).get('manager_contact') or '').strip()
    if contact:
        subject=subject.replace(contact,'[联系方式受限]');body=body.replace(contact,'[联系方式受限]')
    if module=='interpretation' and not status_only and not mail_id:
        body=interpretation_chat_body(body)
        extra=interpretation_editor_extras(db,project,body)
        if extra:body+='\n\n'+(extra.replace(contact,'[联系方式受限]') if contact else extra)
    at=business_now();day=at.date();label=LABELS[module]
    if db.get_bind().dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':int(day.strftime('%Y%m%d'))+{'interpretation':82000000,'annotation':83000000,'recruitment':84000000}[module]})
    from chat_session_category_models import ChatSessionCategory as Category, ChatSessionCategoryFolder as Folder
    from discussion_chat_models import DiscussionMember, DiscussionMessage
    from translation_chat_delivery import people,resolve_audience
    folder_id=uuid5(NAMESPACE_URL,f'xinshi:{module}:date:{day}')
    room_id=uuid5(NAMESPACE_URL,f'xinshi:{module}:project:{project_id}:{day}')
    # 日期只决定首次归档位置；后续保存始终沿用该订单最早的有效会话。
    original=next((row for row in db.query(ProjectChatDispatch).filter_by(module=module,project_id=project_id).order_by(ProjectChatDispatch.created_at,ProjectChatDispatch.request_key) if db.get(Category,row.room_id)),None)
    if original:
        room_id=original.room_id;folder_id=UUID(original.snapshot['folder_id'])
        from datetime import date
        day=date.fromisoformat(original.snapshot['day'])
    client=project.client or (project.sub_client.parent_client if project.sub_client else None)
    title=' · '.join([project.order_no,(client.client_short_name or client.client_name) if client else '未填写客户',project.project_name or '未命名项目'])
    if not db.get(Category,folder_id):
        db.add(Category(id=folder_id,name=f'{label}项目 · {day:%y%m%d}',active=True,revision=1,updated_by=actor.id));db.flush()
        db.add(Folder(category_id=folder_id,parent_key=ROOTS[module]))
    if not db.get(Category,room_id):
        db.add(Category(id=room_id,name=title[:65]+f' · {day:%y%m%d}',active=True,revision=1,updated_by=actor.id));db.flush()
        db.add(Folder(category_id=room_id,parent_key=str(folder_id)))
    members=people(db)
    extra_ids=resolve_audience(db,audience,{str(person.id) for person in members})
    existing={uid for uid, in db.query(DiscussionMember.user_id).filter_by(room_id=room_id)}
    for person in members:
        if person.id not in existing:db.add(DiscussionMember(room_id=room_id,user_id=person.id,last_read_id=0,pinned=False,starred=False))
    db.flush()
    from automatic_project_notice import mark_automatic
    message=DiscussionMessage(room_id=room_id,sender_id=actor.id,sender_name=actor.full_name or actor.username,client_message_id=request_key,content=mark_automatic(subject+'\n\n'+body))
    db.add(message);db.flush()
    if module=='interpretation':
        from interpretation_settings import mention_ids
        target_ids=mention_ids(db,members)
        if project.project_status=='candidates_provided':
            from project_client_manager import attach as attach_manager
            attach_manager(db,'interpretation',[project])
            manager_id=getattr(project,'client_manager_id',None)
            manager_name=getattr(project,'current_client_manager',None)
            target_ids={str(manager_id)} if manager_id else {str(person.id) for person in members if manager_name in {person.full_name,person.username}}
    else:
        # 标注、招聘不依赖邮件组或邮箱是否已配置。
        target_ids={str(project.client_manager_id)} if project.client_manager_id else set()
        for assignment in project.role_assignments:
            if assignment.get('assignee_id'):target_ids.add(str(assignment['assignee_id']))
            target_ids.update(str(value) for value in assignment.get('assignee_ids',[]))
    target_ids.update(extra_ids)
    targets={person.id:person for person in members if person.id!=actor.id and str(person.id) in target_ids}
    from discussion_mentions import create as create_mentions
    notifications=create_mentions(db,actor,message,SimpleNamespace(mention_all='all' in audience),list(targets.values()),existing|{item.id for item in members})
    db.add(ProjectChatDispatch(request_key=request_key,module=module,project_id=project_id,room_id=room_id,actor_id=actor.id,mail_id=mail_id,
                              snapshot={'title':title,'folder_id':str(folder_id),'day':day.isoformat(),'subject':subject,'message_id':str(message.id),'emergency_notice':emergency or subject.startswith(URGENT)}))
    db.commit()
    try:
        from project_chat_crud import _push_notifications
        from discussion_chat_service import publish
        _push_notifications(notifications);publish(db)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('项目会话已保存，实时推送暂未完成')
    return {'room_id':str(room_id),'sent':True}


def complete_mail_intent(db,mail,actor):
    if mail.project_type not in LABELS or mail.status!='sent' or not ready(db):return
    if not db.get(ProjectMailChatIntent,mail.id):return
    from business_mail_service import PROJECT_FK_FIELDS
    try:
        # 复用以通用 business_mail 为外键的历史提醒快照表，保证邮件失败后重试仍使用原名单。
        from translation_chat_delivery import TranslationMailChatIntent
        saved_audience=db.get(TranslationMailChatIntent,mail.id) if inspect(db.connection()).has_table(TranslationMailChatIntent.__tablename__) else None
        send(db,actor,mail.project_type,getattr(mail,PROJECT_FK_FIELDS[mail.project_type]),uuid5(NAMESPACE_URL,'project-mail:'+str(mail.id)),mail_id=mail.id,audience=saved_audience.audience if saved_audience else ())
        intent=db.get(ProjectMailChatIntent,mail.id);intent.error=None;db.commit()
    except Exception as error:
        db.rollback();intent=db.get(ProjectMailChatIntent,mail.id);intent.error=str(getattr(error,'detail',error))[:2000];db.commit()


router=APIRouter(prefix='/project-delivery',tags=['项目发送'],dependencies=[Depends(require_any_permission('projects:write'))])
class ChatSend(BaseModel):
    request_key:UUID
    emergency_notice:bool=False
    audience:list[str]=Field(default_factory=list,max_length=1000)
    status_change_id:UUID|None=None

@router.get('/audience')
def audience_catalog(db=Depends(get_db)):
    from department_models import Department
    from translation_chat_delivery import people
    departments=sorted(db.query(Department).all(),key=lambda row:row.name)
    return {'audience':[{'value':'all','label':'全体'}]+[{'value':'department:'+str(row.id),'label':row.name} for row in departments]+[{'value':'user:'+str(row.id),'label':row.full_name or row.username} for row in people(db)]}

@router.post('/{module}/{project_id}/chat')
def send_endpoint(module:Literal['interpretation','annotation','recruitment'],project_id:UUID,payload:ChatSend,db=Depends(get_db),actor=Depends(get_current_user)):
    try:return send(db,actor,module,project_id,payload.request_key,emergency=payload.emergency_notice,audience=payload.audience,status_change_id=payload.status_change_id)
    except Exception:
        db.rollback();raise


@router.post('/mail/{mail_id}/chat/retry')
def retry_mail_chat(mail_id:UUID,db=Depends(get_db),actor=Depends(get_current_user)):
    from business_mail_models import BusinessMail
    require_ready(db)
    mail=db.get(BusinessMail,mail_id)
    if not mail or mail.project_type not in LABELS:raise HTTPException(404,'项目邮件不存在')
    if mail.status!='sent':raise HTTPException(422,'请先成功发送邮件')
    if not db.get(ProjectMailChatIntent,mail_id):raise HTTPException(422,'该邮件未选择会话联动')
    complete_mail_intent(db,mail,actor)
    error=db.get(ProjectMailChatIntent,mail_id).error
    if error:raise HTTPException(502,error)
    return {'sent':True}
