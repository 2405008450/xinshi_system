"""客户开票资料与办公室开票主体共享目录。"""
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import Column,String,Uuid,JSON,Integer,DateTime,ForeignKey,inspect
from models import Base,Client,SubClient
from database import get_db
from routers.auth import require_permission,require_any_permission
from annotation_progress_time import business_now,business_datetime

SUBJECTS={'guangzhou':('广州','广州信实翻译服务有限公司'),
          'shenzhen':('深圳','广州信实翻译服务有限公司深圳分公司'),
          'shanghai':('上海','广州信实翻译服务有限公司上海分公司')}
SubjectKey=Literal['guangzhou','shenzhen','shanghai']
InvoiceType=Literal['electronic_special','electronic_normal','paper_special','paper_normal']
INVOICE_TYPES={'electronic_special':'电子专票','electronic_normal':'电子普票',
               'paper_special':'纸质专票','paper_normal':'纸质普票'}


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


class SubClientInvoiceProfile(Base):
    __tablename__ = 'sub_client_invoice_profile'
    sub_client_id = Column(Uuid, ForeignKey('sub_client.id', ondelete='CASCADE'), primary_key=True)
    subject_key = Column(String(30), ForeignKey('organization_invoice_subject.key'))
    invoice_kind = Column(String(20))
    data = Column(JSON, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    updated_by = Column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


class PartyWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=0)
    party:InvoiceParty


class ClientProfileWrite(PartyWrite):
    subject_key:SubjectKey|None=None
    invoice_kind:Literal['normal','special']|None=None
    invoice_type:InvoiceType|None=None
    subject_keys:list[SubjectKey]|None=Field(default=None,max_length=30)
    parties:list[InvoiceParty]|None=Field(default=None,max_length=30)


class OrderInvoiceSelectionWrite(BaseModel):
    project_id:UUID
    revision:int=Field(ge=0)
    subject_key:SubjectKey|None=None
    invoice_type:InvoiceType|None=None


class OrderInvoiceSelectionsWrite(BaseModel):
    items:list[OrderInvoiceSelectionWrite]=Field(min_length=1,max_length=100)
    settlement_scope:Literal['special']|None=None


def require_ready(db):
    schema=inspect(db.connection())
    if not all(schema.has_table(table) for table in (OrganizationInvoiceSubject.__tablename__,ClientInvoiceProfile.__tablename__)):
        raise HTTPException(503,'客户及主体开票信息表尚未初始化')


def party_value(row,title=None):
    values={key:value for key,value in (row.data if row else {}).items() if not key.startswith('_')}
    value=InvoiceParty.model_validate(values).model_dump()
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


def get_sub_client(db, client_id, sub_client_id, *, lock=False):
    query = db.query(SubClient).filter_by(id=sub_client_id, parent_client_id=client_id)
    row = (query.with_for_update() if lock else query).first()
    if row is None:
        raise HTTPException(404, '子客户不存在或不属于该客户')
    return row


def profile(db, client_id, sub_client_id=None):
    require_ready(db)
    client=db.get(Client,client_id)
    if client is None:raise HTTPException(404,'客户不存在')
    if sub_client_id:
        buyer = get_sub_client(db, client_id, sub_client_id)
        row = db.get(SubClientInvoiceProfile, sub_client_id) if sub_profile_ready(db) else None
    else:
        buyer = client
        row = db.get(ClientInvoiceProfile,client_id)
    return {'client_id':str(client_id),'client_name':client.client_name,'party':party_value(row),
            'parties':(row.data or {}).get('_parties',[party_value(row)]) if row else [],
            'subject_keys':(row.data or {}).get('_subject_keys',[row.subject_key] if row.subject_key else []) if row else [],
            'sub_client_id':str(sub_client_id) if sub_client_id else None,
            'buyer_name':buyer.client_name or buyer.client_short_name,
            'subject_key':row.subject_key if row else None,'subject':subject(db,row.subject_key) if row and row.subject_key else None,
            'invoice_kind':row.invoice_kind if row else None,'revision':row.revision if row else 0,
            'invoice_type':client_invoice_type(row),
            'updated_at':business_datetime(row.updated_at).isoformat() if row else None}


def sub_profile_ready(db):
    return inspect(db.connection()).has_table(SubClientInvoiceProfile.__tablename__)


def project_invoice_profile(db, client_id, sub_client_id=None):
    return profile(db, client_id, sub_client_id) if sub_client_id else profile(db, client_id)


def client_invoice_type(row):
    if row and (row.data or {}).get('_invoice_type') in INVOICE_TYPES:
        return row.data['_invoice_type']
    return 'electronic_special' if row and row.invoice_kind=='special' else 'electronic_normal'


def order_invoice_selections(db, ids, *, special_roots=None):
    from translation_document_requirements import TranslationProjectDocuments,ready
    from invoice_workflow import latest_invoice_selections

    if not ids:
        return {}
    if special_roots:
        from translation_special_settlement import settings_by_project
        settings=settings_by_project(db,set(special_roots.values()))
        return {str(uid):settings.get(root,{}).get(str(uid),{}).get('invoice_selection',{})
                for uid,root in special_roots.items()}
    stored={}
    if ready(db):
        for document in db.query(TranslationProjectDocuments).filter(TranslationProjectDocuments.project_id.in_(ids)):
            if '_invoice_selection' in (document.quotation_data or {}):
                stored[str(document.project_id)]=document.quotation_data['_invoice_selection']
    return {**latest_invoice_selections(db,[uid for uid in ids if str(uid) not in stored]),**stored}


def effective_invoice_selection(order, default_subject, default_type):
    subject=order.get('subject_key') or default_subject
    invoice_type=order.get('invoice_type') or default_type
    return {'subject_key':subject,'invoice_type':invoice_type,'revision':order.get('revision',0),
            'order_subject_key':order.get('subject_key'),'order_invoice_type':order.get('invoice_type'),
            'client_subject_key':default_subject,'client_invoice_type':default_type}


def invoice_subject_default(client_subject, statement_subjects):
    return client_subject or (next(iter(statement_subjects)) if len(statement_subjects)==1 else None)


def store_order_invoice_selection(db, project_id, subject_key, invoice_type, actor_id, *, revision=None, special_root=None):
    from translation_document_requirements import TranslationProjectDocuments,ready
    if not ready(db):
        raise HTTPException(503,'项目单据存储尚未初始化')
    document_id=special_root or project_id
    row=db.get(TranslationProjectDocuments,document_id)
    data=dict(row.quotation_data or {}) if row else {}
    previous=(data.get('_special_settlement',{}).get(str(project_id),{}).get('invoice_selection')
              if special_root else data.get('_invoice_selection')) or {}
    current=previous.get('revision',0)
    if revision is not None and revision!=current:
        raise HTTPException(409,'订单开票选择已更新，请刷新后再编辑')
    if previous and previous.get('subject_key')==subject_key and previous.get('invoice_type')==invoice_type:
        return
    if row is None:
        row=TranslationProjectDocuments(project_id=document_id,quotation_revision=0)
        db.add(row)
    selection={'subject_key':subject_key,'invoice_type':invoice_type,'revision':current+1}
    if special_root:
        from translation_special_settlement import update_order_data
        update_order_data(row, project_id, {'invoice_selection': selection}, actor_id, business_now())
        db.flush()
        return
    row.quotation_data={**data,'_invoice_selection':selection}
    row.updated_by=actor_id
    row.updated_at=business_now()


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


@router.get('/clients/{client_id}/buyers')
def buyers(client_id:UUID,db=Depends(get_db),actor=Depends(READ)):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(404, '客户不存在')
    children = db.query(SubClient).filter_by(parent_client_id=client_id).order_by(SubClient.sub_client_code, SubClient.id)
    return {'client': {'name': client.client_name or client.client_short_name, 'code': client.client_code},
            'sub_clients': [{'id': str(child.id), 'name': child.client_name or child.client_short_name,
                             'code': child.sub_client_code} for child in children]}


@router.get('/clients/{client_id}/sub-clients/{sub_client_id}')
def read_sub_profile(client_id:UUID,sub_client_id:UUID,db=Depends(get_db),actor=Depends(READ)):
    return profile(db, client_id, sub_client_id)


@router.get('/clients/{client_id}/records')
def records(client_id:UUID,keyword:str|None=None,required:bool|None=None,invoice_status:Literal['unissued','partial','issued']|None=None,
            skip:int=Query(0,ge=0),limit:int=Query(10,ge=1,le=100),db=Depends(get_db),actor=Depends(READ),
            settlement_scope:Literal['standard','special']|None=None,
            invoice_buyer:Literal['client','sub_clients']|UUID|None=None):
    client = db.get(Client, client_id)
    if client is None:raise HTTPException(404,'客户不存在')
    import crud
    from translation_customer_finance import tree,order_billing_month,attach_monthly_payment_peers
    from translation_project_invoices import attach
    from translation_document_requirements import TranslationProjectDocuments,ready,attach as attach_documents
    import translation_special_settlement as special_settlement
    from search_matching import matches_keywords
    special=settlement_scope=='special'
    projects=crud.get_translation_projects(db,skip=0,limit=None,keyword=None if special else keyword,field_filters={'finance_client_ids':{'value':[str(client_id)]}})
    if isinstance(invoice_buyer, UUID):
        get_sub_client(db, client_id, invoice_buyer)
    if settlement_scope:
        from translation_document_requirements import matches_statement_scope
        attach_documents(db,projects)
        projects=[project for project in projects if matches_statement_scope(project,settlement_scope)]
    attach_monthly_payment_peers(db, projects)
    items=[tree(project,summary_only=True)['item'] for project in projects]
    if invoice_buyer == 'client':
        items = [item for item in items if not item['document_sub_client_id']]
    elif invoice_buyer == 'sub_clients':
        items = [item for item in items if item['document_sub_client_id']]
    elif isinstance(invoice_buyer, UUID):
        items = [item for item in items if item['document_sub_client_id'] == str(invoice_buyer)]
    items = [{**item, 'sub_client_id': item['document_sub_client_id']} for item in items]
    if special:
        settings=special_settlement.settings_by_project(db,[project.id for project in projects])
        special_items=[]
        for root in items:
            data=settings.get(UUID(root['id']),{})
            special_settlement.apply_settings(root,data)
            for node in special_settlement.order_nodes(root):
                if matches_keywords(f"{node['order_no']} {node['project_name'] or ''}",keyword):
                    special_items.append({**node,**special_settlement.invoice_state(data.get(node['id'],{})),
                                          'billing_totals':special_settlement.billing_totals(node)})
        items=special_items
    else:
        attach(db,{'items':items})
    summary={'projects':len(items),'required':sum(item['invoice_required'] is True for item in items),
             'issued':sum(item['invoice_status']=='issued' for item in items),'partial':sum(item['invoice_status']=='partial' for item in items),
             'unissued':sum(item['invoice_status']=='unissued' for item in items),'not_required':sum(item['invoice_required'] is False for item in items)}
    items=[item for item in items if (required is None or item['invoice_required']==required) and (invoice_status is None or item['invoice_status']==invoice_status)]
    total=len(items);items=items[skip:skip+limit]
    ids=[UUID(item['id']) for item in items]
    roots={UUID(item['id']):UUID(item['root_id']) for item in items} if special else {}
    selections=order_invoice_selections(db,ids,special_roots=roots)
    client_profile=db.get(ClientInvoiceProfile,client_id) if inspect(db.connection()).has_table(ClientInvoiceProfile.__tablename__) else None
    sub_ids = {UUID(item['sub_client_id']) for item in items if item.get('sub_client_id')}
    sub_profiles = {}
    if sub_ids and sub_profile_ready(db):
        sub_profiles = {str(row.sub_client_id): row for row in db.query(SubClientInvoiceProfile).filter(
            SubClientInvoiceProfile.sub_client_id.in_(sub_ids))}
    from customer_statement_workspace import invoice_subjects_by_order
    statement_subjects=invoice_subjects_by_order(db,client_id,special=special)
    proofs={str(row.project_id):(row.quotation_data or {}).get('_invoice',{}).get('proofs','') for row in db.query(TranslationProjectDocuments).filter(TranslationProjectDocuments.project_id.in_(ids))} if not special and ids and ready(db) else {}
    def default_profile(item):
        return sub_profiles.get(item['sub_client_id']) if item.get('sub_client_id') else client_profile

    rows=[{**{key:item.get(key) for key in ('id','root_id','order_no','project_name','invoice_status','invoice_required','billing_totals','effective_billing_tax_mode','sub_client_id')},
           'invoice_buyer_name': (item.get('sub_client_short_name') or item.get('sub_client_code') or '子客户')
               if item.get('sub_client_id') else (client.client_short_name or client.client_name),
           'billing_month':item.get('billing_month') or order_billing_month(item['order_no']),
           'invoice_proofs':item.get('proofs','') if special else proofs.get(item['id'],''),
           'special':special,
           'invoice_selection':effective_invoice_selection(selections.get(item['id'],{}),
               invoice_subject_default(getattr(default_profile(item), 'subject_key', None),statement_subjects.get(item['root_id'],set())),
               client_invoice_type(default_profile(item)))} for item in items]
    return {'items':rows,'total':total,'summary':summary}


@router.put('/clients/{client_id}')
def update_profile(client_id:UUID,payload:ClientProfileWrite,db=Depends(get_db),actor=Depends(require_permission('clients:write'))):
    require_ready(db)
    if db.query(Client).filter_by(id=client_id).with_for_update().first() is None:raise HTTPException(404,'客户不存在')
    save_profile(db, ClientInvoiceProfile, 'client_id', client_id, payload, actor)
    return profile(db, client_id)


@router.put('/clients/{client_id}/sub-clients/{sub_client_id}')
def update_sub_profile(client_id:UUID,sub_client_id:UUID,payload:ClientProfileWrite,
                       db=Depends(get_db),actor=Depends(require_permission('clients:write'))):
    require_ready(db)
    get_sub_client(db, client_id, sub_client_id, lock=True)
    if not sub_profile_ready(db):
        raise HTTPException(503, '子客户开票信息表尚未初始化')
    save_profile(db, SubClientInvoiceProfile, 'sub_client_id', sub_client_id, payload, actor)
    return profile(db, client_id, sub_client_id)


def save_profile(db, model, id_field, buyer_id, payload, actor):
    identity = {id_field: buyer_id}
    row=db.query(model).filter_by(**identity).with_for_update().populate_existing().first()
    if payload.revision!=(row.revision if row else 0):raise HTTPException(409,'客户开票资料已更新，请重新打开后编辑')
    if payload.subject_key and db.get(OrganizationInvoiceSubject,payload.subject_key) is None:raise HTTPException(422,'开票主体尚未初始化')
    if row is None:
        row = model(**identity, revision=0)
        db.add(row)
    data=payload.party.model_dump()
    for key,value in (('_subject_keys',payload.subject_keys),('_parties',payload.parties)):
        if value is not None:
            if key=='_subject_keys':
                if len(set(value))!=len(value):raise HTTPException(422,'开票主体不能重复')
                for subject_key in value:
                    if db.get(OrganizationInvoiceSubject,subject_key) is None:raise HTTPException(422,'开票主体尚未初始化')
                data[key]=value
            else:data[key]=[item.model_dump() for item in value]
        elif row and key in (row.data or {}):data[key]=row.data[key]
    if data.get('_parties'):
        data['_parties'][0]=payload.party.model_dump()
    if payload.subject_key and '_subject_keys' in data:
        data['_subject_keys']=[payload.subject_key,*[key for key in data['_subject_keys'] if key!=payload.subject_key]]
    if payload.invoice_type:
        data['_invoice_type']=payload.invoice_type
    elif 'invoice_type' not in payload.model_fields_set and 'invoice_kind' not in payload.model_fields_set and (row.data or {}).get('_invoice_type'):
        data['_invoice_type']=row.data['_invoice_type']
    row.data=data;row.subject_key=payload.subject_key
    row.invoice_kind=payload.invoice_type.rsplit('_',1)[-1] if payload.invoice_type else payload.invoice_kind
    row.revision+=1;row.updated_by=actor.id;row.updated_at=business_now();db.commit()


@router.put('/order-selections')
def update_order_selections(payload:OrderInvoiceSelectionsWrite,db=Depends(get_db),
                            actor=Depends(require_any_permission('clients:write','projects:write','finance:write'))):
    from models import TranslationProject
    ids={item.project_id for item in payload.items}
    if len(ids)!=len(payload.items):
        raise HTTPException(422,'订单不能重复')
    roots={}
    if payload.settlement_scope=='special':
        from translation_project_invoices import special_root_ids
        roots=special_root_ids(db,ids)
    root_ids=set(roots.values()) if roots else ids
    locked=db.query(TranslationProject.id).filter(
        TranslationProject.id.in_(root_ids),TranslationProject.annotation_migrated_at.is_(None),
    ).order_by(TranslationProject.id).with_for_update().all()
    if len(locked)!=len(root_ids):
        raise HTTPException(404,'订单不存在')
    if roots:
        from translation_document_requirements import attach, payment_method
        projects=db.query(TranslationProject).filter(TranslationProject.id.in_(root_ids)).all()
        attach(db,projects)
        if any(payment_method(project)!='special' for project in projects):
            raise HTTPException(422,'所选订单必须属于特殊结算')
    for item in payload.items:
        store_order_invoice_selection(db,item.project_id,item.subject_key,item.invoice_type,actor.id,
                                      revision=item.revision,special_root=roots.get(item.project_id))
    db.commit()
    return {'updated':len(ids)}
