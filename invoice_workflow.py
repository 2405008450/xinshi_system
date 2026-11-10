"""发票负责人、主动发送开票需求及发票文件附件。"""
from uuid import UUID,uuid4
from urllib.parse import quote
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Response
from pydantic import BaseModel,Field
from sqlalchemy import Column,Uuid,String,JSON,Integer,DateTime,ForeignKey,LargeBinary,inspect
from sqlalchemy.exc import IntegrityError
from models import Base,AppUser,TranslationProject,AppNotification
from database import get_db
from routers.auth import get_current_user,require_any_permission,user_has_permission
from annotation_progress_time import business_now,business_datetime


class InvoiceSettings(Base):
    __tablename__='finance_invoice_settings'
    key=Column(String(30),primary_key=True)
    user_ids=Column(JSON)
    revision=Column(Integer,nullable=False,default=1)
    updated_by=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


class InvoiceRequest(Base):
    __tablename__='finance_invoice_request'
    id=Column(Uuid,primary_key=True,default=uuid4)
    idempotency_key=Column(String(64),nullable=False,unique=True)
    project_id=Column(Uuid,ForeignKey('translation_project.id'),nullable=False,index=True)
    client_id=Column(Uuid,ForeignKey('client.id'),nullable=False,index=True)
    subject_key=Column(String(30),ForeignKey('organization_invoice_subject.key'),nullable=False)
    recipients=Column(JSON,nullable=False)
    snapshot=Column(JSON,nullable=False)
    created_by=Column(Uuid,ForeignKey('app_user.id'),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


class InvoiceAttachment(Base):
    __tablename__='finance_invoice_attachment'
    id=Column(Uuid,primary_key=True,default=uuid4)
    project_id=Column(Uuid,ForeignKey('translation_project.id'),nullable=False,index=True)
    name=Column(String(255),nullable=False)
    content_type=Column(String(200),nullable=False)
    size=Column(Integer,nullable=False)
    content=Column(LargeBinary,nullable=False)
    uploaded_by=Column(Uuid,ForeignKey('app_user.id'),nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


def require_ready(db):
    if not all(inspect(db.connection()).has_table(model.__tablename__) for model in (InvoiceSettings,InvoiceRequest,InvoiceAttachment)):
        raise HTTPException(503,'发票设置、需求与附件表尚未初始化')


def directory(db):
    from organization_service import department_condition
    customers={person.id for person in db.query(AppUser).filter(department_condition(db,['客户部']))}
    users=db.query(AppUser).filter(AppUser.is_active.is_(True),AppUser.is_deleted.is_(False)).all()
    users.sort(key=lambda person:(person.id not in customers,person.full_name or person.username,str(person.id)))
    return [{'id':str(person.id),'name':person.full_name or person.username,'username':person.username,
             'department':person.department or '', 'customer_department':person.id in customers} for person in users]


def settings(db):
    require_ready(db);people=directory(db);allowed={person['id'] for person in people}
    row=db.get(InvoiceSettings,'invoice')
    ids=row.user_ids if row and row.user_ids is not None else [person['id'] for person in people if person['name'].strip()=='熊旺' or person['username']=='熊旺']
    return {'user_ids':[uid for uid in ids if uid in allowed],'users':people,'revision':row.revision if row else 0,'rule_based':not row or row.user_ids is None}


class SettingsWrite(BaseModel):
    revision:int=Field(ge=0)
    user_ids:list[UUID]=Field(min_length=1,max_length=500)


class RequestWrite(BaseModel):
    project_id:UUID
    subject_key:Literal['guangzhou','shenzhen','shanghai']
    settings_revision:int
    expected_user_ids:list[UUID]=Field(min_length=1,max_length=500)
    idempotency_key:str=Field(min_length=8,max_length=64)
    note:str=Field(default='',max_length=2000)


def request_value(row):
    return {'id':str(row.id),'project_id':str(row.project_id),'client_id':str(row.client_id),'subject_key':row.subject_key,
            'recipients':row.recipients,'snapshot':row.snapshot,'created_at':business_datetime(row.created_at).isoformat()}


def send_request(db,actor,payload):
    from invoice_parties import profile,subject
    from translation_project_invoices import read as read_invoice
    require_ready(db)
    project=db.query(TranslationProject).filter_by(id=payload.project_id).with_for_update().first()
    if project is None:raise HTTPException(404,'项目不存在')
    previous=db.query(InvoiceRequest).filter_by(idempotency_key=payload.idempotency_key).first()
    if previous:
        if previous.created_by!=actor.id or previous.project_id!=project.id:raise HTTPException(409,'需求发送标识不匹配')
        return request_value(previous)
    config=settings(db)
    if config['revision']!=payload.settings_revision or set(config['user_ids'])!={str(uid) for uid in payload.expected_user_ids}:
        raise HTTPException(409,'开票负责人设置已更新，请重新打开后核对')
    if not config['user_ids']:raise HTTPException(422,'请在财务设置选择开票负责人')
    invoice=read_invoice(db,project.id)
    if not invoice.get('client_id'):raise HTTPException(422,'请先为项目关联客户')
    client=profile(db,UUID(invoice['client_id']));issuer=subject(db,payload.subject_key)
    names={person['id']:person['name'] for person in config['users']}
    snapshot={'order_no':invoice['order_no'],'project_name':project.source_file_name or project.project_name,
              'client_name':client['client_name'],'client_party':client['party'],'invoice_kind':client['invoice_kind'],
              'subject':issuer,'totals':invoice['totals'],'red_required':invoice.get('red_required',False),
              'note':payload.note,'sender':actor.full_name or actor.username,
              'recipient_names':[names[uid] for uid in config['user_ids']]}
    row=InvoiceRequest(id=uuid4(),idempotency_key=payload.idempotency_key,project_id=project.id,client_id=UUID(invoice['client_id']),
        subject_key=payload.subject_key,recipients=config['user_ids'],snapshot=snapshot,created_by=actor.id,created_at=business_now())
    db.add(row)
    notices=[];moment=business_now()
    content=f"订单：{invoice['order_no']}\n客户：{client['client_name']}\n开票主体：{issuer['name']}\n发送人：{snapshot['sender']}\n说明：{payload.note or '-'}"
    for uid in config['user_ids']:
        notice=AppNotification(id=uuid4(),recipient_user_id=UUID(uid),title=f"开票需求 · {invoice['order_no']}"[:255],content=content,
            notification_type='invoice_request',related_project_id=project.id,related_project_type='invoice_request',related_entity_id=row.id,
            is_read=False,created_at=moment.replace(tzinfo=None));db.add(notice);notices.append(notice)
    db.commit()
    from notification_ws import dispatch_personal_message
    from schemas import NotificationResponse
    for notice in notices:dispatch_personal_message(notice.recipient_user_id,{'type':'notification','notification':NotificationResponse.model_validate(notice).model_dump(mode='json')})
    return request_value(row)


def attachment_value(row):return {'id':str(row.id),'name':row.name,'size':row.size,'content_type':row.content_type,'created_at':business_datetime(row.created_at).isoformat()}


def attachment_list(db,ids):
    if not ids:return []
    if not inspect(db.connection()).has_table(InvoiceAttachment.__tablename__):return []
    rows={str(row.id):row for row in db.query(InvoiceAttachment).filter(InvoiceAttachment.id.in_([UUID(str(uid)) for uid in ids]))}
    return [attachment_value(rows[str(uid)]) for uid in ids if str(uid) in rows]


router=APIRouter(prefix='/invoice-workflow',tags=['发票工作流'])
READ=require_any_permission('projects:read','projects:write','clients:read','clients:write','finance:read','finance:write')
WRITE=require_any_permission('projects:write','finance:write','clients:write')


@router.get('/settings')
def read_settings(db=Depends(get_db),actor=Depends(READ)):return settings(db)


@router.put('/settings')
def update_settings(payload:SettingsWrite,db=Depends(get_db),actor=Depends(require_any_permission('projects:write','finance:write','system:users:write'))):
    current=settings(db);allowed={person['id'] for person in current['users']}
    if len(set(payload.user_ids))!=len(payload.user_ids) or any(str(uid) not in allowed for uid in payload.user_ids):raise HTTPException(422,'请从在用公司人员中选择负责人，不能重复')
    row=db.query(InvoiceSettings).filter_by(key='invoice').with_for_update().populate_existing().first()
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'财务设置已更新，请重新加载')
    if row is None:row=InvoiceSettings(key='invoice',revision=0);db.add(row)
    row.user_ids=[str(uid) for uid in payload.user_ids];row.revision+=1;row.updated_by=actor.id;row.updated_at=business_now();db.commit();return settings(db)


@router.post('/requests')
def create_request(payload:RequestWrite,db=Depends(get_db),actor=Depends(WRITE)):
    try:return send_request(db,actor,payload)
    except IntegrityError:db.rollback();raise HTTPException(409,'发送记录发生冲突，请重新打开后核对')
    except Exception:db.rollback();raise


@router.get('/requests/{request_id}')
def read_request(request_id:UUID,db=Depends(get_db),actor=Depends(get_current_user)):
    require_ready(db);row=db.get(InvoiceRequest,request_id)
    if row is None:raise HTTPException(404,'开票需求不存在')
    if actor.id!=row.created_by and str(actor.id) not in row.recipients and not any(user_has_permission(db,actor.id,code) for code in ('projects:write','finance:write')):raise HTTPException(403,'无权查看该开票需求')
    return request_value(row)


@router.post('/projects/{project_id}/attachments')
async def upload_attachment(project_id:UUID,file:UploadFile=File(...),db=Depends(get_db),actor=Depends(WRITE)):
    require_ready(db)
    if db.get(TranslationProject,project_id) is None:raise HTTPException(404,'项目不存在')
    content=await file.read(20*1024*1024+1)
    if not content or len(content)>20*1024*1024:raise HTTPException(422,'文件不能为空，且每个文件不能超过20MB')
    name=(file.filename or '发票附件').replace('\\','/').split('/')[-1].replace('\x00','')[:255]
    row=InvoiceAttachment(id=uuid4(),project_id=project_id,name=name or '发票附件',content_type=(file.content_type or 'application/octet-stream')[:200],size=len(content),content=content,uploaded_by=actor.id,created_at=business_now())
    db.add(row);db.commit();return attachment_value(row)


@router.get('/attachments/{attachment_id}')
def download_attachment(attachment_id:UUID,db=Depends(get_db),actor=Depends(READ)):
    require_ready(db);row=db.get(InvoiceAttachment,attachment_id)
    if row is None:raise HTTPException(404,'附件不存在')
    from translation_document_requirements import TranslationProjectDocuments
    doc=db.get(TranslationProjectDocuments,row.project_id)
    linked=str(row.id) in ((doc.quotation_data or {}).get('_invoice',{}).get('attachments',[]) if doc else [])
    if not linked and row.uploaded_by!=actor.id:
        import translation_finance_audit as audit
        from translation_finance_audit import TranslationFinanceEventItem,TranslationFinanceEvent
        history=db.query(TranslationFinanceEventItem).join(TranslationFinanceEvent,TranslationFinanceEvent.id==TranslationFinanceEventItem.event_id).filter(TranslationFinanceEvent.project_id==row.project_id).all() if audit.ready(db) else []
        if not any(str(row.id) in str(item.before_snapshot) or str(row.id) in str(item.after_snapshot) for item in history):raise HTTPException(403,'附件尚未保存到发票记录')
    return Response(content=bytes(row.content),media_type='application/octet-stream',headers={'Content-Disposition':f"attachment; filename*=UTF-8''{quote(row.name,safe='')}",'X-Content-Type-Options':'nosniff'})
