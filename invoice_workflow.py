"""发票负责人、主动发送开票需求及发票文件附件。"""
from decimal import Decimal
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

INVOICE_TYPES = {'electronic_special':'电子专票', 'electronic_normal':'电子普票',
                 'paper_special':'纸质专票', 'paper_normal':'纸质普票'}
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


class BatchSelection(BaseModel):
    project_ids: list[UUID] = Field(min_length=1, max_length=100)


class BatchWrite(BatchSelection):
    subject_key: Literal['guangzhou','shenzhen','shanghai']
    invoice_type: Literal['electronic_special','electronic_normal','paper_special','paper_normal']
    tax_rate: Literal[1, 3, 6] | None = None
    settings_revision: int
    expected_user_ids: list[UUID] = Field(min_length=1, max_length=500)
    idempotency_key: UUID
    note: str = Field(default='', max_length=2000)


class ReceiptWrite(BaseModel):
    project_id: UUID | None = None


class DeliveryWrite(BaseModel):
    version: str


def selected_incl_totals(node):
    if not node.get('price_aggregate'):
        if node.get('effective_billing_tax_mode') != 'incl_tax':
            return {}
        return {currency: Decimal(str(amount)) for currency, amount in node.get('billing_totals', {}).items()}
    totals = {}
    for child in node.get('children', []):
        for currency, amount in selected_incl_totals(child).items():
            totals[currency] = totals.get(currency, Decimal(0)) + amount
    return totals


def batch_projects(db, project_ids):
    from crud import get_translation_project
    from invoice_parties import profile
    from translation_customer_finance import tree
    if len(set(project_ids)) != len(project_ids):
        raise HTTPException(422, '项目不能重复')
    projects = []
    for project_id in project_ids:
        project = get_translation_project(db, project_id)
        if project is None:
            raise HTTPException(404, '项目不存在')
        node = tree(project, include_version=False)['item']
        amounts = selected_incl_totals(node)
        if not amounts:
            raise HTTPException(422, f'{project.order_no} 没有选定的含税金额')
        if not node.get('client_id'):
            raise HTTPException(422, f'{project.order_no} 尚未关联客户')
        client = profile(db, UUID(node['client_id']))
        projects.append({'project_id': str(project.id), 'order_no': project.order_no,
                         'project_name': project.source_file_name or project.project_name,
                         'client_id': client['client_id'], 'client_name': client['client_name'],
                         'client_party': client['party'], 'default_subject': client['subject_key'],
                         'totals': {currency: str(amount) for currency, amount in amounts.items()}})
    return projects


def customer_groups(projects):
    groups = {}
    for project in projects:
        client_id = project['client_id']
        group = groups.setdefault(client_id, {'client_id': client_id, 'project_ids': [], 'totals': {}})
        group['project_ids'].append(project['project_id'])
        totals = group['totals']
        for currency, amount in (project.get('totals') or {}).items():
            totals[currency] = totals.get(currency, Decimal(0)) + Decimal(str(amount))
    return [{**group, 'totals': {currency: format(amount, '.2f') for currency, amount in group['totals'].items()}}
            for group in groups.values()]


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


def send_batch(db, actor, payload):
    from invoice_parties import subject
    require_ready(db)
    key = str(payload.idempotency_key)
    # Lock the selected orders in a stable order so a retry sees the committed request.
    db.query(TranslationProject.id).filter(TranslationProject.id.in_(payload.project_ids)).order_by(TranslationProject.id).with_for_update().all()
    previous = db.query(InvoiceRequest).filter_by(idempotency_key=key).first()
    submission = payload.model_dump(mode='json', exclude={'idempotency_key'})
    if previous:
        if previous.created_by != actor.id or previous.snapshot.get('submission') != submission:
            raise HTTPException(409, '需求发送标识不匹配')
        return request_value(previous, actor)
    projects = batch_projects(db, payload.project_ids)
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
    snapshot = {'projects': projects, 'subject': issuer, 'invoice_type': INVOICE_TYPES[payload.invoice_type],
                'tax_rate': payload.tax_rate, 'note': payload.note, 'sender': actor.full_name or actor.username,
                'recipient_names': [names[uid] for uid in config['user_ids']], 'submission': submission}
    row = InvoiceRequest(id=uuid4(), idempotency_key=key, project_id=UUID(first['project_id']),
        client_id=UUID(first['client_id']), subject_key=payload.subject_key, recipients=config['user_ids'],
        snapshot=snapshot, created_by=actor.id, created_at=business_now())
    db.add(row)
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


def require_invoice_recipient(db, request_id, actor):
    row = accessible_request(db, request_id, actor)
    if str(actor.id) not in row.recipients:
        raise HTTPException(403, '仅开票接收人可操作')
    return row


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
    projects = batch_projects(db, payload.project_ids)
    return {'projects': projects, 'customer_groups': customer_groups(projects),
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
        row.snapshot = {**row.snapshot, 'deliveries': {**deliveries, project['project_id']: {**delivery, 'receipt': receipt}}}
        target = UUID(delivery['sender_id'])
        title, content = '发票收到回执', f"{name}已确认收到 {project['order_no']} 的发票。"
    commit_notices(db, [create_notice(db, row, target, 'invoice_receipt', title, content)])
    return request_value(row, actor)


@router.get('/requests/{request_id}/projects/{project_id}/invoice')
def read_request_invoice(request_id: UUID, project_id: UUID, db=Depends(get_db), actor=Depends(get_current_user)):
    from translation_project_invoices import read
    row = accessible_request(db, request_id, actor)
    workflow_project(row, project_id)
    delivery = row.snapshot.get('deliveries', {}).get(str(project_id))
    if str(actor.id) not in row.recipients and not delivery:
        raise HTTPException(409, '该项目尚未发送发票')
    invoice = read(db, project_id)
    if delivery:
        invoice.update(proofs=delivery['proofs'], invoice_status='issued')
    return invoice


@router.put('/requests/{request_id}/projects/{project_id}/invoice')
def save_request_invoice(request_id: UUID, project_id: UUID, payload: InvoiceWrite, db=Depends(get_db), actor=Depends(get_current_user)):
    from translation_project_invoices import save
    row = accessible_request(db, request_id, actor, lock=True)
    if str(actor.id) not in row.recipients:
        raise HTTPException(403, '仅开票接收人可操作')
    if str(actor.id) not in row.snapshot.get('request_receipts', {}):
        raise HTTPException(409, '请先发送开票需求的收到回执')
    workflow_project(row, project_id)
    if str(project_id) in row.snapshot.get('deliveries', {}):
        raise HTTPException(409, '该项目的发票已发送')
    return save(db, project_id, payload, actor.id)


@router.post('/requests/{request_id}/projects/{project_id}/deliver')
def deliver_invoice(request_id: UUID, project_id: UUID, payload: DeliveryWrite, db=Depends(get_db), actor=Depends(get_current_user)):
    row = accessible_request(db, request_id, actor, lock=True)
    if str(actor.id) not in row.recipients:
        raise HTTPException(403, '仅开票接收人可发送发票')
    if str(actor.id) not in row.snapshot.get('request_receipts', {}):
        raise HTTPException(409, '请先发送开票需求的收到回执')
    workflow_project(row, project_id)
    if str(project_id) in row.snapshot.get('deliveries', {}):
        return request_value(row, actor)
    complete_deliveries(db, [row], project_id, actor, payload.version)
    return request_value(row, actor)


def pending_invoice_requests(db, project_id, actor, *, lock=False):
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
            and (any(project['project_id'] == key for project in row.snapshot['projects'])
                 if 'projects' in row.snapshot else row.project_id == project_id)]


@router.post('/projects/{project_id}/notify-issued')
def notify_issued(project_id: UUID, payload: DeliveryWrite, db=Depends(get_db), actor=Depends(BATCH_WRITE)):
    rows = pending_invoice_requests(db, project_id, actor, lock=True)
    if rows:
        complete_deliveries(db, rows, project_id, actor, payload.version)
    return {'notified': len(rows)}


def complete_deliveries(db, rows, project_id, actor, version):
    from editor_screenshot_service import valid_references
    from translation_project_invoices import read, record_completion_notice
    db.query(TranslationProject.id).filter_by(id=project_id).with_for_update().first()
    invoice = read(db, project_id)
    if invoice['version'] != version:
        raise HTTPException(409, '发票资料已更新，请重新打开核对后发送')
    if invoice['invoice_status'] != 'issued' or not valid_references(invoice['proofs']):
        raise HTTPException(422, '请先上传发票附件并保存为已开票')
    moment = business_now()
    delivery = {'proofs': invoice['proofs'], 'sender_id': str(actor.id),
                'sender': actor.full_name or actor.username, 'at': moment.isoformat()}
    notices = []
    for row in rows:
        project = workflow_project(row, project_id)
        deliveries = {**row.snapshot.get('deliveries', {}), str(project_id): delivery}
        row.snapshot = {**row.snapshot, 'deliveries': deliveries}
        notices.append(create_notice(db, row, row.created_by, 'invoice_delivered',
                       f"开票完成 · {project['order_no']}", f"{delivery['sender']}已开票并发送发票，请确认收到。"))
    record_completion_notice(db, project_id, actor, moment)
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
