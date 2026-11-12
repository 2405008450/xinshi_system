"""共享母订单发票入口：复用财务发票状态与项目单据 JSON，不创建新表。"""
import hashlib,json
from uuid import UUID,uuid4
from typing import Literal
from pydantic import BaseModel,Field
from fastapi import HTTPException
from models import TranslationProject,FinanceRecord,AppUser
from annotation_progress_time import business_now
import translation_document_requirements as documents


class InvoiceWrite(BaseModel):
    version:str
    invoice_status:Literal['unissued','partial','issued']='unissued'
    proofs:str=Field(default='',max_length=20000)


class InvoiceCustomerSentWrite(BaseModel):
    sent: bool


def document_invoice(doc):
    return (doc.quotation_data or {}).get('_invoice', {}) if doc else {}


def action_value(actor, moment):
    return {'name': actor.full_name or actor.username, 'at': moment.isoformat()}


def update_document_invoice(doc, invoice, actor_id, moment):
    doc.quotation_data = {**(doc.quotation_data or {}), '_invoice': invoice}
    doc.updated_by = actor_id
    doc.updated_at = moment


def invoice_required(node):
    if node.get('price_aggregate'):
        required=[invoice_required(child) for child in node['children']]
        return True if True in required else None if None in required or not required else False
    mode=node.get('effective_billing_tax_mode')
    return True if mode=='incl_tax' else False if mode=='excl_tax' else None


def read(db,project_id,order_id=None):
    from translation_customer_finance import read as read_finance
    data=read_finance(db,project_id);root=data['item']
    def find(node):return node if node['id']==str(order_id or project_id) else next((found for child in node.get('children',[]) if (found:=find(child))),None)
    node=find(root)
    if node is None:raise HTTPException(404,'订单不属于该笔译项目')
    record=db.query(FinanceRecord).filter_by(project_id=project_id).first()
    doc=db.get(documents.TranslationProjectDocuments,project_id) if documents.ready(db) else None
    invoice = document_invoice(doc)
    state={'invoice_status':record.invoice_status if record else 'unissued','proofs':invoice.get('proofs',''),
           'issued_by':invoice.get('issued_by'), 'issued_notification':invoice.get('issued_notification'),
           'customer_sent':invoice.get('customer_sent')}
    version=hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest()
    return {**state,'version':version,'project_id':str(project_id),'order_id':node['id'],'order_no':node['order_no'],
            'client_id':root.get('client_id'),'client_name':root.get('client_short_name') or '-','required':invoice_required(node),
            'tax_mode':node.get('effective_billing_tax_mode'),'totals':node.get('billing_totals',{}),
            'note':(root.get('document_notes') or {}).get('invoice',''),'payment_version':data['payment']['version']}


def save(db,project_id,payload,actor_id,order_id=None):
    import translation_finance_audit as audit
    from crud import get_translation_project
    from editor_screenshot_service import references,valid_references,ready,promote_business_references,now,api_time
    from editor_screenshot_models import EditorScreenshot
    audit.require_ready(db)
    project=db.query(TranslationProject).filter_by(id=project_id).with_for_update().populate_existing().first()
    if project is None:raise HTTPException(404,'笔译项目不存在')
    project=get_translation_project(db,project_id)
    current=read(db,project_id,order_id)
    if current['version']!=payload.version:raise HTTPException(409,'发票信息已更新，请重新加载后核对')
    refs=references(payload.proofs)
    if refs:
        if refs!=valid_references(payload.proofs):raise HTTPException(422,'发票截图引用无效')
        if not ready(db):raise HTTPException(503,'截图功能尚未初始化')
        images=db.query(EditorScreenshot).filter(EditorScreenshot.id.in_(refs)).all()
        if len(images)!=len(refs) or any(not image.blob_sha256 or image.expires_at and api_time(image.expires_at)<=now() for image in images):raise HTTPException(422,'发票截图不存在或已过期')
        promote_business_references(db,refs)
    if not documents.ready(db):raise HTTPException(503,'项目单据存储尚未初始化')
    project.invoice_data = {key:current[key] for key in ('invoice_status', 'proofs')}
    project.invoice_data.update({key:current[key] for key in ('issued_by', 'issued_notification', 'customer_sent') if current[key]})
    before=audit.capture(project)
    moment=business_now()
    record=db.query(FinanceRecord).filter_by(project_id=project_id).with_for_update().first()
    if record is None:
        record=FinanceRecord(id=uuid4(),project_id=project_id,created_at=moment.replace(tzinfo=None));db.add(record)
    record.invoice_status=payload.invoice_status;record.edited_by=actor_id;record.updated_at=moment.replace(tzinfo=None)
    doc=db.get(documents.TranslationProjectDocuments,project_id)
    if doc is None:
        doc=documents.TranslationProjectDocuments(project_id=project_id,quotation_revision=0);db.add(doc)
    state = {**document_invoice(doc), 'invoice_status':payload.invoice_status, 'proofs':payload.proofs}
    actor = db.get(AppUser, actor_id)
    if payload.invoice_status == 'issued' and (current['invoice_status'] != 'issued' or not current['issued_by']):
        state['issued_by'] = action_value(actor, moment)
    elif payload.invoice_status != 'issued':
        state.pop('issued_by', None)
        state.pop('issued_notification', None)
    update_document_invoice(doc, state, actor_id, moment)
    project.invoice_data=state
    db.flush();audit.append(db,actor,project,before);db.commit()
    return {**read(db,project_id,order_id),'previous_payment_version':current['payment_version']}


def record_completion_notice(db, project_id, actor, moment):
    doc = db.get(documents.TranslationProjectDocuments, project_id)
    invoice = document_invoice(doc)
    action = action_value(actor, moment)
    update_document_invoice(doc, {**invoice, 'issued_by':invoice.get('issued_by') or action,
                                  'issued_notification':action}, actor.id, moment)


def set_customer_sent(db, project_id, actor, sent):
    if not documents.ready(db):
        raise HTTPException(503, '项目单据存储尚未初始化')
    if not db.query(TranslationProject.id).filter_by(id=project_id).with_for_update().first():
        raise HTTPException(404, '笔译项目不存在')
    doc = db.get(documents.TranslationProjectDocuments, project_id)
    invoice = document_invoice(doc)
    if bool(invoice.get('customer_sent')) == sent:
        return {'customer_sent': invoice.get('customer_sent')}
    if sent:
        record = db.query(FinanceRecord).filter_by(project_id=project_id).first()
        if not record or record.invoice_status != 'issued':
            raise HTTPException(422, '请先确认已开票')
    moment = business_now()
    action = action_value(actor, moment) if sent else None
    if doc is None:
        doc = documents.TranslationProjectDocuments(project_id=project_id, quotation_revision=0)
        db.add(doc)
    update_document_invoice(doc, {**invoice, 'customer_sent':action}, actor.id, moment)
    db.commit()
    return {'customer_sent': action}


def attach(db,result):
    ids=[UUID(item['id']) for item in result.get('items',[])]
    states={str(project_id):status for project_id,status in db.query(FinanceRecord.project_id,FinanceRecord.invoice_status).filter(FinanceRecord.project_id.in_(ids))} if ids else {}
    doc_model = documents.TranslationProjectDocuments
    details = ({str(doc.project_id): document_invoice(doc) for doc in db.query(doc_model).filter(doc_model.project_id.in_(ids))}
               if ids and documents.ready(db) else {})
    for item in result.get('items',[]):
        pending=[item]
        while pending:
            node=pending.pop();node['invoice_status']=states.get(item['id'],'unissued');node['invoice_required']=invoice_required(node)
            invoice = details.get(item['id'], {})
            for field in ('issued_by', 'issued_notification', 'customer_sent'):
                node[field] = invoice.get(field)
            pending.extend(node.get('children',[]))
    return result
