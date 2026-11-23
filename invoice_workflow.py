"""发票负责人、主动发送开票需求及发票文件附件。"""
from decimal import Decimal
import hashlib
from uuid import UUID,uuid4
from urllib.parse import quote
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Response
from pydantic import BaseModel,Field,SecretStr
from sqlalchemy import Column,Uuid,String,JSON,Integer,DateTime,ForeignKey,LargeBinary,inspect,cast,or_
from sqlalchemy.exc import IntegrityError
from models import Base,AppUser,TranslationProject,AppNotification
from database import get_db
from routers.auth import get_current_user,require_any_permission
from annotation_progress_time import business_now,business_datetime
from translation_project_invoices import InvoiceWrite
from invoice_parties import (
    INVOICE_TYPES, InvoiceType, effective_invoice_selection, invoice_subject_default,
    order_invoice_selections, store_order_invoice_selection,
)

TEST_RECIPIENT_USERNAME = 'invoice_receiver_test'

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
    customers={person.id for person in db.query(AppUser).filter(department_condition(db,['客户部','销售部']))}
    users=db.query(AppUser).filter(AppUser.is_active.is_(True),AppUser.is_deleted.is_(False)).all()
    users.sort(key=lambda person:(person.id not in customers,person.full_name or person.username,str(person.id)))
    return [{'id':str(person.id),'name':person.full_name or person.username,'username':person.username,
             'department':person.department or '', 'customer_department':person.id in customers} for person in users]


def settings(db):
    require_ready(db);people=directory(db);allowed={person['id'] for person in people}
    row=db.get(InvoiceSettings,'invoice')
    ids = list(row.user_ids) if row and row.user_ids is not None else [
        person['id'] for person in people if person['name'].strip() == '熊旺'
        or person['username'].casefold() in {'熊旺', 'sales3@xinshifanyi.com.cn'}
    ]
    return {'user_ids':[uid for uid in ids if uid in allowed],'users':people,'revision':row.revision if row else 0,'rule_based':not row or row.user_ids is None}


def batch_settings(db):
    config = settings(db)
    test_ids = [person['id'] for person in config['users'] if person['username'] == TEST_RECIPIENT_USERNAME]
    config['user_ids'] = list(dict.fromkeys(config['user_ids'] + test_ids))
    return config


class SettingsWrite(BaseModel):
    revision:int=Field(ge=0)
    user_ids:list[UUID]=Field(min_length=1,max_length=500)


class TestRecipientWrite(BaseModel):
    password: SecretStr


class RequestWrite(BaseModel):
    project_id:UUID
    subject_key:Literal['guangzhou','shenzhen','shanghai']
    settings_revision:int
    expected_user_ids:list[UUID]=Field(min_length=1,max_length=500)
    idempotency_key:str=Field(min_length=8,max_length=64)
    note:str=Field(default='',max_length=2000)


from statement_invoice_documents import StatementInvoiceRef

class BatchSelection(BaseModel):
    project_ids: list[UUID] = Field(default_factory=list, max_length=100)
    statement_refs:list[StatementInvoiceRef]=Field(default_factory=list,max_length=100)
    client_party_choices:dict[UUID,int]=Field(default_factory=dict)
    settlement_scope: Literal['special'] | None = None


class BatchWrite(BatchSelection):
    subject_key: Literal['guangzhou','shenzhen','shanghai']
    invoice_type: InvoiceType = 'electronic_normal'
    tax_rate: Literal[1, 3, 6] | None = None
    settings_revision: int
    expected_user_ids: list[UUID] = Field(min_length=1, max_length=500)
    idempotency_key: UUID
    note: str = Field(default='', max_length=2000)
    selection_revisions: dict[UUID,int] | None = None


class ReceiptWrite(BaseModel):
    project_id: UUID | None = None


class DeliveryWrite(BaseModel):
    version: str


def selected_incl_totals(node):
    if node.get('effective_billing_tax_mode') == 'incl_tax':
        return {currency: Decimal(str(amount)) for currency, amount in node.get('billing_totals', {}).items()}
    if not node.get('price_aggregate'):
        return {}
    totals = {}
    for child in node.get('children', []):
        for currency, amount in selected_incl_totals(child).items():
            totals[currency] = totals.get(currency, Decimal(0)) + amount
    return totals


def latest_invoice_selections(db, ids):
    if not ids or not inspect(db.connection()).has_table(InvoiceRequest.__tablename__):
        return {}
    requested={str(uid) for uid in ids}
    query=db.query(InvoiceRequest).filter(or_(InvoiceRequest.project_id.in_(ids),
        *(cast(InvoiceRequest.snapshot,String).contains(uid) for uid in requested),
    )).order_by(InvoiceRequest.created_at.desc(),InvoiceRequest.id.desc())
    found={}
    labels={label:key for key,label in INVOICE_TYPES.items()}
    for request in query:
        snapshot=request.snapshot
        members=({item.get('project_id') for item in snapshot['projects'] if not item.get('root_id')}
                 if 'projects' in snapshot else {str(request.project_id)})
        invoice_type=(snapshot.get('submission') or {}).get('invoice_type') or labels.get(snapshot.get('invoice_type'))
        for uid in requested & members:
            found.setdefault(uid,{'subject_key':request.subject_key,'invoice_type':invoice_type,'revision':0})
        if requested <= found.keys():
            break
    return found


def batch_projects(db, project_ids, *, special=False):
    from translation_price_rollup import price_details
    from crud import get_translation_project
    from invoice_parties import project_invoice_profile
    from translation_customer_finance import attach_monthly_payment_peers, settlement_group_key, tree
    from translation_document_requirements import attach as attach_documents
    from translation_project_invoices import special_order, special_root_ids
    import translation_special_settlement as special_settlement
    if len(set(project_ids)) != len(project_ids):
        raise HTTPException(422, '项目不能重复')
    projects = []
    statement_subjects = {}
    roots = special_root_ids(db, project_ids) if special else {}
    settings = special_settlement.settings_by_project(db, set(roots.values()))
    selections=order_invoice_selections(db,project_ids,special_roots=roots)
    selected = {str(order_id) for order_id in project_ids}
    for project_id in project_ids:
        project = get_translation_project(db, roots.get(project_id, project_id))
        if project is None:
            raise HTTPException(404, '项目不存在')
        attach_documents(db, [project])
        attach_monthly_payment_peers(db, [project])
        node = tree(project, include_version=False)['item']
        if special:
            node = special_order(node, settings.get(project.id, {}), project_id)
            if node.get('price_aggregate') and any(child['id'] in selected for child in special_settlement.order_nodes(node) if child is not node):
                raise HTTPException(422, '已选择汇总订单，请取消勾选其下级订单，避免重复开票')
            amounts = special_settlement.billing_totals(node, tax_mode='incl_tax')
        else:
            if node.get('payment_method') == 'special':
                raise HTTPException(422, '请从特殊结算发票发起开票需求')
            amounts = selected_incl_totals(node)
        if not amounts:
            raise HTTPException(422, f"{node['order_no']} 没有选定的含税金额")
        if not node.get('client_id'):
            raise HTTPException(422, f'{project.order_no} 尚未关联客户')
        sub_id = node.get('document_sub_client_id', node.get('sub_client_id'))
        client = project_invoice_profile(db, UUID(node['client_id']), UUID(sub_id) if sub_id else None)
        client_id = client['client_id']
        if client_id not in statement_subjects:
            from customer_statement_workspace import invoice_subjects_by_order
            statement_subjects[client_id] = invoice_subjects_by_order(db, UUID(client_id), special=special)
        subjects = statement_subjects[client_id].get(str(node.get('root_id') or project.id), set())
        fallback_subject=invoice_subject_default(client['subject_key'],subjects)
        selection=effective_invoice_selection(selections.get(str(project_id),{}),fallback_subject,client['invoice_type'])
        sub_group = {
            'sub_client_id': sub_id, 'sub_client_name': client.get('buyer_name') or node['sub_client_short_name'],
            'sub_client_code': node['sub_client_code'], 'invoice_buyer_group': f'sub-client:{sub_id}',
        } if sub_id else {}
        if not special and node['payment_method']=='sub_client':
            _,month,period,_,sub_id=settlement_group_key(project)
            sub_group['settlement_group'] = f'{sub_id}:{month}:{period}'
        projects.append({'project_id': str(project_id), **({'root_id':str(project.id)} if special else {}), **sub_group,
                         'order_no': node['order_no'], 'project_name': node['project_name'],
                         'client_id': client['client_id'], 'client_name': client['client_name'],
                         'client_party': client['party'], 'client_party_options':client.get('parties') or [client['party']], 'default_subject': selection['subject_key'],
                         'invoice_selection':selection,'client_invoice_subject':client['subject_key'],'price_details':price_details(node),
                         'totals': {currency: str(amount) for currency, amount in amounts.items()}})
    return projects


def customer_groups(projects):
    groups = {}
    for project in projects:
        client_id = project['client_id']
        key = invoice_group_identity(project)
        group = groups.setdefault(key, {'client_id': client_id, 'project_ids': [], 'totals': {},
            **({'group_id':key} if key != client_id else {})})
        group['project_ids'].append(project['project_id'])
        totals = group['totals']
        for currency, amount in (project.get('totals') or {}).items():
            totals[currency] = totals.get(currency, Decimal(0)) + Decimal(str(amount))
    return [{**group, 'totals': {currency: format(amount, '.2f') for currency, amount in group['totals'].items()}}
            for group in groups.values()]


def invoice_group_identity(project):
    return project.get('settlement_group') or project.get('invoice_buyer_group') or project.get('client_id')


def create_notice(db, row, recipient, kind, title, content):
    notice = AppNotification(id=uuid4(), recipient_user_id=recipient, title=title[:255], content=content,
        notification_type=kind, related_project_id=row.project_id, related_project_type='invoice_request',
        related_entity_id=row.id, is_read=False, created_at=business_now().replace(tzinfo=None))
    db.add(notice)
    return notice


def commit_notices(db, notices):
    from notification_ws import dispatch_personal_message
    from schemas import NotificationResponse
    db.commit()
    for notice in notices:
        dispatch_personal_message(notice.recipient_user_id, {
            'type':'notification', 'notification':NotificationResponse.model_validate(notice).model_dump(mode='json'),
        })


def apply_party_choices(projects,choices):
    for project in projects:
        index=choices.get(UUID(project['client_id']),0)
        options=project.get('client_party_options') or [project['client_party']]
        if index<0 or index>=len(options):raise HTTPException(422,'客户开票信息已变化，请重新选择')
        project['client_party']=options[index]


def send_batch(db, actor, payload):
    from invoice_parties import subject
    require_ready(db)
    if payload.invoice_type.endswith('_special') and payload.subject_key=='guangzhou' and payload.tax_rate is None:
        payload=payload.model_copy(update={'tax_rate':6})
    key = str(payload.idempotency_key)
    # Lock the selected orders in a stable order so a retry sees the committed request.
    special = payload.settlement_scope == 'special'
    if special:
        from translation_project_invoices import special_root_ids
        roots = special_root_ids(db, payload.project_ids)
    else:
        roots = {}
    db.query(TranslationProject.id).filter(TranslationProject.id.in_(roots.values() if special else payload.project_ids)).order_by(TranslationProject.id).with_for_update().all()
    previous = db.query(InvoiceRequest).filter_by(idempotency_key=key).first()
    submission = payload.model_dump(mode='json', exclude={'idempotency_key'})
    if payload.selection_revisions is None:
        submission.pop('selection_revisions')
    if not special:
        submission.pop('settlement_scope')
    if previous:
        if previous.created_by != actor.id or previous.snapshot.get('submission') != submission:
            raise HTTPException(409, '需求发送标识不匹配')
        return request_value(previous, actor)
    documents=[]
    if payload.statement_refs:
        if not special:raise HTTPException(422,'对账单开票仅用于特殊结算')
        from statement_invoice_documents import read_documents,invoice_projects
        documents=read_documents(db,payload.statement_refs);projects=invoice_projects(db,documents)
    else:
        if not payload.project_ids:raise HTTPException(422,'请选择项目或特殊结算对账单')
        from statement_invoice_documents import read_documents,invoice_projects
    documents=read_documents(db,payload.statement_refs) if payload.statement_refs else []
    if documents and not special:raise HTTPException(422,'对账单开票请使用特殊结算发票')
    if not documents and not payload.project_ids:raise HTTPException(422,'请选择项目或对账单')
    projects = invoice_projects(db,documents) if documents else batch_projects(db, payload.project_ids, special=special)
    apply_party_choices(projects,payload.client_party_choices)
    if payload.invoice_type.endswith('_special'):
        allowed = {6} if payload.subject_key == 'guangzhou' else {1, 3}
        if payload.tax_rate not in allowed:
            raise HTTPException(422, '专票税率须匹配开票主体：广州 6%，深圳或上海 1% / 3%')
    elif payload.tax_rate is not None:
        raise HTTPException(422, '普票无需选择专票税率')
    config = batch_settings(db)
    if config['revision'] != payload.settings_revision or set(config['user_ids']) != {str(uid) for uid in payload.expected_user_ids}:
        raise HTTPException(409, '开票接收人设置已更新，请重新打开后核对')
    issuer = subject(db, payload.subject_key)
    first = projects[0]
    names = {person['id']: person['name'] for person in config['users']}
    snapshot = {'statements':documents,'projects': projects, 'subject': issuer, 'invoice_type': INVOICE_TYPES[payload.invoice_type],
                'tax_rate': payload.tax_rate, 'note': payload.note, 'sender': actor.full_name or actor.username,
                'recipient_names': [names[uid] for uid in config['user_ids']], 'submission': submission}
    row = InvoiceRequest(id=uuid4(), idempotency_key=key, project_id=UUID(first.get('root_id',first['project_id'])),
        client_id=UUID(first['client_id']), subject_key=payload.subject_key, recipients=config['user_ids'],
        snapshot=snapshot, created_by=actor.id, created_at=business_now())
    db.add(row)
    if payload.selection_revisions is not None and payload.selection_revisions.keys()!=set(payload.project_ids):
        raise HTTPException(422,'请重新加载所有订单的开票选择')
    for project in ([] if documents else projects):
        project_id=UUID(project['project_id'])
        store_order_invoice_selection(db,project_id,payload.subject_key,payload.invoice_type,actor.id,
                                      revision=payload.selection_revisions[project_id] if payload.selection_revisions is not None else None,
                                      special_root=roots.get(project_id))
    title = f"开票需求 · {first['order_no']}" + (f' 等 {len(projects)} 个项目' if len(projects) > 1 else '')
    notices = [create_notice(db, row, UUID(uid), 'invoice_request', title,
                             f"{snapshot['sender']}发来{snapshot['invoice_type']}开票需求，请确认收到。")
               for uid in config['user_ids']]
    commit_notices(db, notices)
    return request_value(row, actor)


def request_value(row, actor=None):
    snapshot = {key: value for key, value in row.snapshot.items() if key != 'submission'}
    projects = snapshot.get('projects')
    if projects is None:
        projects = [{**snapshot, 'project_id': str(row.project_id), 'client_id': str(row.client_id)}]
    return {'id':str(row.id),'project_id':str(row.project_id),'client_id':str(row.client_id),'subject_key':row.subject_key,
            'recipients':row.recipients,'snapshot':snapshot,'customer_groups':customer_groups(projects),
            'created_at':business_datetime(row.created_at).isoformat(),
            'is_sender': bool(actor and actor.id == row.created_by),
            'is_recipient': bool(actor and str(actor.id) in row.recipients)}


def accessible_request(db, request_id, actor, *, lock=False):
    require_ready(db)
    query = db.query(InvoiceRequest).filter_by(id=request_id)
    row = (query.with_for_update().populate_existing() if lock else query).first()
    if row is None:
        raise HTTPException(404, '开票需求不存在')
    if actor.id != row.created_by and str(actor.id) not in row.recipients:
        raise HTTPException(403, '无权查看该开票需求')
    return row


def workflow_project(row, project_id):
    projects = row.snapshot.get('projects')
    if projects is None and row.project_id == project_id:
        return {'project_id': str(project_id), 'order_no': row.snapshot.get('order_no', '')}
    project = next((item for item in projects or [] if item['project_id'] == str(project_id)), None)
    if project is None:
        raise HTTPException(404, '项目不在本次开票需求中')
    return project


def invoice_group(row, project_id, combined):
    project = workflow_project(row, project_id)
    members = [item for item in row.snapshot.get('projects', []) if invoice_group_identity(item) == invoice_group_identity(project)]
    if len(members) < 2:
        return [project]
    deliveries = row.snapshot.get('deliveries', {})
    if any(item['project_id'] in deliveries and not deliveries[item['project_id']].get('combined_invoice_id') for item in members):
        if combined:
            raise HTTPException(409, '该组已有逐单发送的发票，请继续查看各订单的原发票')
        return [project]
    return members


def invoice_identity(project):
    order_id = UUID(project['project_id'])
    root_id = project.get('root_id')
    return (UUID(root_id) if root_id else order_id), order_id, bool(root_id)


def group_invoice(db, projects, *, lock=False):
    from translation_project_invoices import read
    identities = [invoice_identity(project) for project in projects]
    if lock:
        roots = {root for root, _, _ in identities}
        db.query(TranslationProject.id).filter(TranslationProject.id.in_(roots)).order_by(
            TranslationProject.id).with_for_update().all()
    records = [read(db, root, order, special=special) for root, order, special in identities]
    invoice = records[0]
    if len(records) == 1:
        return invoice, records
    group = customer_groups(projects)[0]
    versions = '\n'.join(record['version'] for record in records)
    return {**invoice, 'version': hashlib.sha256(versions.encode()).hexdigest(), 'required': True,
            'totals': group['totals'], 'price_details':None}, records


def needs_combined_delivery(row, key):
    projects = row.snapshot.get('projects', [])
    project = next((item for item in projects if item['project_id'] == key), None)
    if not project:
        return False
    group = [item for item in projects if invoice_group_identity(item) == invoice_group_identity(project)]
    deliveries = row.snapshot.get('deliveries', {})
    return len(group) > 1 and not any(item['project_id'] in deliveries and
        not deliveries[item['project_id']].get('combined_invoice_id') for item in group)


def require_invoice_recipient(db, request_id, actor):
    row = accessible_request(db, request_id, actor)
    if str(actor.id) not in row.recipients:
        raise HTTPException(403, '仅开票接收人可操作')
    return row


def send_request(db,actor,payload):
    from invoice_parties import project_invoice_profile,subject
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
    sub_id = invoice.get('sub_client_id')
    client = project_invoice_profile(db, UUID(invoice['client_id']), UUID(sub_id) if sub_id else None)
    issuer=subject(db,payload.subject_key)
    names={person['id']:person['name'] for person in config['users']}
    buyer_name = client.get('buyer_name') or client['client_name']
    snapshot={'order_no':invoice['order_no'],'project_name':project.source_file_name or project.project_name,
              'client_name':buyer_name,'client_party':client['party'],'invoice_kind':client['invoice_kind'],
              'subject':issuer,'totals':invoice['totals'],'red_required':invoice.get('red_required',False),
              'note':payload.note,'sender':actor.full_name or actor.username,
              'recipient_names':[names[uid] for uid in config['user_ids']]}
    row=InvoiceRequest(id=uuid4(),idempotency_key=payload.idempotency_key,project_id=project.id,client_id=UUID(invoice['client_id']),
        subject_key=payload.subject_key,recipients=config['user_ids'],snapshot=snapshot,created_by=actor.id,created_at=business_now())
    db.add(row)
    notices=[];moment=business_now()
    content=f"订单：{invoice['order_no']}\n客户：{buyer_name}\n开票主体：{issuer['name']}\n发送人：{snapshot['sender']}\n说明：{payload.note or '-'}"
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
BATCH_WRITE = require_any_permission('projects:write','finance:write')


@router.get('/settings')
def read_settings(db=Depends(get_db),actor=Depends(require_any_permission('projects:read','projects:write','finance:read','finance:write','system:users:write'))):
    return settings(db)


@router.post('/settings/test-recipient', status_code=201)
def create_test_recipient(payload: TestRecipientWrite, db=Depends(get_db), actor=Depends(require_any_permission('system:users:write'))):
    from crud import create_user, get_user_by_username
    from schemas import AppUserCreate
    require_ready(db)
    if get_user_by_username(db, TEST_RECIPIENT_USERNAME):
        raise HTTPException(409, '发票接收测试账号已存在')
    password = payload.password.get_secret_value()
    if len(password) < 12 or len(password.encode('utf-8')) > 72:
        raise HTTPException(422, '测试账号密码至少 12 个字符，且不超过 72 字节')
    try:
        user = create_user(db, AppUserCreate(username=TEST_RECIPIENT_USERNAME, full_name='发票接收测试账号',
            department='客户部', password=password))
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '发票接收测试账号已存在')
    return {'id': str(user.id), 'username': user.username}


@router.post('/requests/preview')
def preview_batch(payload: BatchSelection, db=Depends(get_db), actor=Depends(BATCH_WRITE)):
    from invoice_parties import SUBJECTS, subject
    config = batch_settings(db)
    documents=[]
    if payload.statement_refs:
        if payload.settlement_scope!='special':raise HTTPException(422,'对账单开票仅用于特殊结算')
        from statement_invoice_documents import read_documents,invoice_projects
        documents=read_documents(db,payload.statement_refs);projects=invoice_projects(db,documents)
    else:
        if not payload.project_ids:raise HTTPException(422,'请选择项目或对账单')
        from statement_invoice_documents import read_documents,invoice_projects
    documents=read_documents(db,payload.statement_refs) if payload.statement_refs else []
    if documents and payload.settlement_scope!='special':raise HTTPException(422,'对账单开票请使用特殊结算发票')
    if not documents and not payload.project_ids:raise HTTPException(422,'请选择项目或对账单')
    projects = invoice_projects(db,documents) if documents else batch_projects(db, payload.project_ids, special=payload.settlement_scope=='special')
    apply_party_choices(projects,payload.client_party_choices)
    return {'statements':documents,'projects': projects, 'customer_groups': customer_groups(projects),
            'subjects': [subject(db, key) for key in SUBJECTS],
            'settings_revision': config['revision'],
            'recipients': [user for user in config['users'] if user['id'] in config['user_ids']]}


@router.post('/requests/batch')
def create_batch(payload: BatchWrite, db=Depends(get_db), actor=Depends(BATCH_WRITE)):
    try:
        return send_batch(db, actor, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '发送记录发生冲突，请重试')


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
    return request_value(accessible_request(db, request_id, actor), actor)


@router.post('/requests/{request_id}/receipts')
def confirm_receipt(request_id: UUID, payload: ReceiptWrite, db=Depends(get_db), actor=Depends(get_current_user)):
    row = accessible_request(db, request_id, actor, lock=True)
    name = actor.full_name or actor.username
    receipt = {'name': name, 'at': business_now().isoformat()}
    if payload.project_id is None:
        uid = str(actor.id)
        if uid not in row.recipients:
            raise HTTPException(403, '仅开票接收人可发送需求回执')
        receipts = row.snapshot.get('request_receipts', {})
        if uid in receipts:
            return request_value(row, actor)
        row.snapshot = {**row.snapshot, 'request_receipts': {**receipts, uid: receipt}}
        target = row.created_by
        title, content = '开票需求收到回执', f'{name}已确认收到开票需求。'
    else:
        if actor.id != row.created_by:
            raise HTTPException(403, '仅需求发送人可确认收到发票')
        project = workflow_project(row, payload.project_id)
        deliveries = row.snapshot.get('deliveries', {})
        delivery = deliveries.get(project['project_id'])
        if not delivery:
            raise HTTPException(409, '该项目尚未发送发票')
        if delivery.get('receipt'):
            return request_value(row, actor)
        combined_id = delivery.get('combined_invoice_id')
        received_ids = [key for key, value in deliveries.items() if value.get('combined_invoice_id') == combined_id] if combined_id else [project['project_id']]
        row.snapshot = {**row.snapshot, 'deliveries': {**deliveries, **{key: {**deliveries[key], 'receipt': receipt} for key in received_ids}}}
        target = UUID(delivery['sender_id'])
        title, content = '发票收到回执', f"{name}已确认收到 {project['order_no']} 的发票。"
    commit_notices(db, [create_notice(db, row, target, 'invoice_receipt', title, content)])
    return request_value(row, actor)


@router.get('/requests/{request_id}/projects/{project_id}/invoice')
def read_request_invoice(request_id: UUID, project_id: UUID, db=Depends(get_db), actor=Depends(get_current_user), combined:bool=False):
    row = accessible_request(db, request_id, actor)
    projects = invoice_group(row, project_id, combined)
    delivery = row.snapshot.get('deliveries', {}).get(str(project_id))
    uploaded = row.snapshot.get('uploaded_invoices', {}).get(str(project_id))
    if str(actor.id) not in row.recipients and not (delivery or uploaded):
        raise HTTPException(409, '发票尚未上传')
    shared = delivery or (uploaded if str(actor.id) not in row.recipients else None)
    if shared:
        project = projects[0]
        current, _ = group_invoice(db, projects)
        return {**current, 'required':True,
                'order_no':project['order_no'],'client_name':project.get('client_name'),
                'price_details':project.get('price_details') if len(projects)==1 else None,
                'totals':customer_groups(projects)[0]['totals'] if len(projects)>1 else project.get('totals',{})}
    invoice, _ = group_invoice(db, projects)
    return invoice


@router.put('/requests/{request_id}/projects/{project_id}/invoice')
def save_request_invoice(request_id: UUID, project_id: UUID, payload: InvoiceWrite, db=Depends(get_db), actor=Depends(get_current_user), combined:bool=False):
    from editor_screenshot_service import valid_references
    from translation_project_invoices import save
    row = accessible_request(db, request_id, actor, lock=True)
    if str(actor.id) not in row.recipients:
        raise HTTPException(403, '仅开票接收人可操作')
    if str(actor.id) not in row.snapshot.get('request_receipts', {}):
        raise HTTPException(409, '请先发送开票需求的收到回执')
    projects = invoice_group(row, project_id, combined)
    current, records = group_invoice(db, projects, lock=True)
    if current['version'] != payload.version:
        raise HTTPException(409, '发票信息已更新，请重新加载后核对')
    for project, record in zip(projects, records):
        root, order, special = invoice_identity(project)
        save(db, root, payload.model_copy(update={'version':record['version']}), actor.id, order, special=special, commit=False)
    uploaded = dict(row.snapshot.get('uploaded_invoices', {}))
    for project in projects:
        key = project['project_id']
        if payload.invoice_status == 'issued' and valid_references(payload.proofs):
            uploaded[key] = {'proofs':payload.proofs}
        else:
            uploaded.pop(key, None)
    row.snapshot = {**row.snapshot, 'uploaded_invoices':uploaded}
    db.commit()
    invoice, _ = group_invoice(db, projects)
    return invoice


@router.post('/requests/{request_id}/projects/{project_id}/deliver')
def deliver_invoice(request_id: UUID, project_id: UUID, payload: DeliveryWrite, db=Depends(get_db), actor=Depends(get_current_user), combined:bool=False):
    row = accessible_request(db, request_id, actor, lock=True)
    if str(actor.id) not in row.recipients:
        raise HTTPException(403, '仅开票接收人可发送发票')
    if str(actor.id) not in row.snapshot.get('request_receipts', {}):
        raise HTTPException(409, '请先发送开票需求的收到回执')
    projects = invoice_group(row, project_id, combined)
    if str(project_id) in row.snapshot.get('deliveries', {}):
        return request_value(row, actor)
    complete_deliveries(db, [row], project_id, actor, payload.version, projects=projects)
    return request_value(row, actor)


def pending_invoice_requests(db, project_id, actor, *, lock=False, special=False):
    if not inspect(db.connection()).has_table(InvoiceRequest.__tablename__):
        return []
    key = str(project_id)
    query = db.query(InvoiceRequest).filter(or_(InvoiceRequest.project_id == project_id,
        cast(InvoiceRequest.snapshot, String).contains(key))).order_by(InvoiceRequest.id)
    if lock:
        query = query.with_for_update().populate_existing()
    uid = str(actor.id)
    return [row for row in query if uid in row.recipients and uid in row.snapshot.get('request_receipts', {})
            and key not in row.snapshot.get('deliveries', {})
            and not needs_combined_delivery(row, key)
            and (any(project['project_id'] == key and bool(project.get('root_id')) == special
                     for project in row.snapshot['projects'])
                 if 'projects' in row.snapshot else not special and row.project_id == project_id)]


@router.post('/projects/{project_id}/notify-issued')
def notify_issued(project_id: UUID, payload: DeliveryWrite, db=Depends(get_db), actor=Depends(BATCH_WRITE), special:bool=False):
    rows = pending_invoice_requests(db, project_id, actor, lock=True,special=special)
    if rows:
        complete_deliveries(db, rows, project_id, actor, payload.version)
    return {'notified': len(rows)}


def complete_deliveries(db, rows, project_id, actor, version, *, projects=None):
    from editor_screenshot_service import valid_references
    from translation_project_invoices import record_completion_notice
    projects = projects or [workflow_project(rows[0], project_id)]
    invoice, records = group_invoice(db, projects, lock=True)
    if invoice['version'] != version:
        raise HTTPException(409, '发票资料已更新，请重新打开核对后发送')
    if not valid_references(invoice['proofs']) or any(record['invoice_status'] != 'issued' or
            record['proofs'] != invoice['proofs'] for record in records):
        raise HTTPException(422, '请先上传发票附件并保存为已开票')
    moment = business_now()
    delivery = {'proofs': invoice['proofs'], 'sender_id': str(actor.id),
                'sender': actor.full_name or actor.username, 'at': moment.isoformat()}
    if len(projects) > 1:
        delivery['combined_invoice_id'] = projects[0]['project_id']
    notices = []
    for row in rows:
        project = workflow_project(row, project_id)
        deliveries = {**row.snapshot.get('deliveries', {}), **{item['project_id']:delivery for item in projects}}
        row.snapshot = {**row.snapshot, 'deliveries': deliveries}
        notices.append(create_notice(db, row, row.created_by, 'invoice_delivered',
                       f"开票完成 · {project['order_no']}", f"{delivery['sender']}已开票并发送发票，请确认收到。"))
    for item in projects:
        root, order, special = invoice_identity(item)
        record_completion_notice(db, root, actor, moment, order_id=order, special=special)
    commit_notices(db, notices)


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
