"""客户开票资料与办公室开票主体共享目录。"""
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import Column,String,Uuid,JSON,Integer,DateTime,ForeignKey,inspect
from models import Base,Client
from database import get_db
from routers.auth import require_permission,require_any_permission
from annotation_progress_time import business_now,business_datetime

SUBJECTS={'guangzhou':('广州','广州信实翻译服务有限公司'),
          'shenzhen':('深圳','广州信实翻译服务有限公司深圳分公司'),
          'shanghai':('上海','广州信实翻译服务有限公司上海分公司')}
SubjectKey=Literal['guangzhou','shenzhen','shanghai']


class InvoiceParty(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(default='',max_length=300)
    tax_number:str=Field(default='',max_length=100)
    address:str=Field(default='',max_length=500)
    phone:str=Field(default='',max_length=100)
    bank:str=Field(default='',max_length=300)
    bank_account:str=Field(default='',max_length=100)
    email:str=Field(default='',max_length=300)
    remarks:str=Field(default='',max_length=2000)


class OrganizationInvoiceSubject(Base):
    __tablename__='organization_invoice_subject'
    key=Column(String(30),primary_key=True)
    data=Column(JSON,nullable=False)
    revision=Column(Integer,nullable=False,default=1)
    updated_by=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


class ClientInvoiceProfile(Base):
    __tablename__='client_invoice_profile'
    client_id=Column(Uuid,ForeignKey('client.id',ondelete='CASCADE'),primary_key=True)
    subject_key=Column(String(30),ForeignKey('organization_invoice_subject.key'))
    invoice_kind=Column(String(20))
    data=Column(JSON,nullable=False)
    revision=Column(Integer,nullable=False,default=1)
    updated_by=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


class PartyWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=0)
    party:InvoiceParty


class ClientProfileWrite(PartyWrite):
    subject_key:SubjectKey|None=None
    invoice_kind:Literal['normal','special']|None=None


def require_ready(db):
    schema=inspect(db.connection())
    if not all(schema.has_table(table) for table in (OrganizationInvoiceSubject.__tablename__,ClientInvoiceProfile.__tablename__)):
        raise HTTPException(503,'客户及主体开票信息表尚未初始化')


def party_value(row,title=None):
    value=InvoiceParty.model_validate(row.data if row else {}).model_dump()
    if title is not None:value['title']=title
    return value


def subject(db,key):
    if key not in SUBJECTS:raise HTTPException(404,'开票主体不存在')
    row=db.get(OrganizationInvoiceSubject,key);city,name=SUBJECTS[key]
    value=party_value(row,name)
    from office_management import default_id
    return {'office_id':str(default_id(city)),'key':key,'city':city,'name':name,'party':value,'revision':row.revision if row else 0,
            'complete':bool(value['tax_number'] and value['address'] and value['phone'] and value['bank'] and value['bank_account']),
            'updated_at':business_datetime(row.updated_at).isoformat() if row else None}


def profile(db,client_id):
    require_ready(db)
    client=db.get(Client,client_id)
    if client is None:raise HTTPException(404,'客户不存在')
    row=db.get(ClientInvoiceProfile,client_id)
    return {'client_id':str(client_id),'client_name':client.client_name,'party':party_value(row),
            'subject_key':row.subject_key if row else None,'subject':subject(db,row.subject_key) if row and row.subject_key else None,
            'invoice_kind':row.invoice_kind if row else None,'revision':row.revision if row else 0,
            'updated_at':business_datetime(row.updated_at).isoformat() if row else None}


router=APIRouter(prefix='/invoice-parties',tags=['客户与主体开票资料'])
READ=require_any_permission('clients:read','clients:write','projects:read','projects:write','finance:read','finance:write','system:users:read','system:users:write','system:organization:write')


@router.get('/subjects')
def subjects(db=Depends(get_db),actor=Depends(READ)):
    require_ready(db);return {'items':[subject(db,key) for key in SUBJECTS]}


@router.put('/subjects/{key}')
def update_subject(key:SubjectKey,payload:PartyWrite,db=Depends(get_db),actor=Depends(require_any_permission('system:users:write','system:organization:write'))):
    require_ready(db)
    row=db.query(OrganizationInvoiceSubject).filter_by(key=key).with_for_update().populate_existing().first()
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'主体开票资料已更新，请重新打开后编辑')
    name=SUBJECTS[key][1]
    if payload.party.title and payload.party.title!=name:raise HTTPException(422,'开票主体名称由系统固定，不能修改')
    if row is None:row=OrganizationInvoiceSubject(key=key,revision=0);db.add(row)
    row.data={**payload.party.model_dump(),'title':name};row.revision+=1;row.updated_by=actor.id;row.updated_at=business_now()
    db.commit();return subject(db,key)


@router.get('/clients/{client_id}')
def read_profile(client_id:UUID,db=Depends(get_db),actor=Depends(READ)):
    return profile(db,client_id)


@router.get('/clients/{client_id}/records')
def records(client_id:UUID,keyword:str|None=None,required:bool|None=None,invoice_status:Literal['unissued','partial','issued']|None=None,
            skip:int=Query(0,ge=0),limit:int=Query(10,ge=1,le=100),db=Depends(get_db),actor=Depends(READ)):
    if db.get(Client,client_id) is None:raise HTTPException(404,'客户不存在')
    import crud
    from translation_customer_finance import tree,order_billing_month
    from translation_project_invoices import attach
    from translation_document_requirements import TranslationProjectDocuments,ready
    projects=crud.get_translation_projects(db,skip=0,limit=None,keyword=keyword,field_filters={'finance_client_id':{'value':str(client_id)}})
    items=[tree(project,summary_only=True)['item'] for project in projects]
    attach(db,{'items':items})
    summary={'projects':len(items),'required':sum(item['invoice_required'] is True for item in items),
             'issued':sum(item['invoice_status']=='issued' for item in items),'partial':sum(item['invoice_status']=='partial' for item in items),
             'unissued':sum(item['invoice_status']=='unissued' for item in items),'not_required':sum(item['invoice_required'] is False for item in items)}
    items=[item for item in items if (required is None or item['invoice_required']==required) and (invoice_status is None or item['invoice_status']==invoice_status)]
    total=len(items);items=items[skip:skip+limit]
    ids=[UUID(item['id']) for item in items]
    proofs={str(row.project_id):(row.quotation_data or {}).get('_invoice',{}).get('proofs','') for row in db.query(TranslationProjectDocuments).filter(TranslationProjectDocuments.project_id.in_(ids))} if ids and ready(db) else {}
    rows=[{**{key:item.get(key) for key in ('id','root_id','order_no','project_name','invoice_status','invoice_required','billing_totals','effective_billing_tax_mode')},
           'billing_month':order_billing_month(item['order_no']),'invoice_proofs':proofs.get(item['id'],'')} for item in items]
    return {'items':rows,'total':total,'summary':summary}


@router.put('/clients/{client_id}')
def update_profile(client_id:UUID,payload:ClientProfileWrite,db=Depends(get_db),actor=Depends(require_permission('clients:write'))):
    require_ready(db)
    if db.query(Client).filter_by(id=client_id).with_for_update().first() is None:raise HTTPException(404,'客户不存在')
    row=db.query(ClientInvoiceProfile).filter_by(client_id=client_id).with_for_update().populate_existing().first()
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'客户开票资料已更新，请重新打开后编辑')
    if payload.subject_key and db.get(OrganizationInvoiceSubject,payload.subject_key) is None:raise HTTPException(422,'开票主体尚未初始化')
    if row is None:row=ClientInvoiceProfile(client_id=client_id,revision=0);db.add(row)
    row.data=payload.party.model_dump();row.subject_key=payload.subject_key;row.invoice_kind=payload.invoice_kind
    row.revision+=1;row.updated_by=actor.id;row.updated_at=business_now();db.commit();return profile(db,client_id)
