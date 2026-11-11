"""笔译项目单据要求与报价内容；对账单内容继续使用既有工作区。"""
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, Uuid, inspect
from fastapi import HTTPException
from models import Base
from annotation_progress_time import business_now


class QuotationLine(BaseModel):
    model_config = ConfigDict(extra='forbid')
    description: str = Field(default='', max_length=1000)
    language_pair: str = Field(default='', max_length=500)
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=4)
    unit: str = Field(default='字', max_length=50)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=4)
    currency: Literal['CNY','USD','HKD','EUR','GBP','JPY'] = 'CNY'


class QuotationDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(default='翻译服务报价单', max_length=255)
    client_name: str = Field(default='', max_length=255)
    items: list[QuotationLine] = Field(default_factory=list, min_length=1, max_length=100)
    notes: str = Field(default='', max_length=5000)


class DocumentNotes(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quotation: str = Field(default='',max_length=2000)
    statement: str = Field(default='',max_length=2000)
    invoice: str = Field(default='',max_length=2000)


def quotation_value(row):
    data={key:value for key,value in (row.quotation_data or {}).items() if not key.startswith('_')} if row else {}
    return data or None


def document_notes(row):
    data=(row.quotation_data or {}).get('_document_notes',{}) if row else {}
    return DocumentNotes.model_validate(data).model_dump()


class TranslationProjectDocuments(Base):
    __tablename__ = 'translation_project_documents'
    project_id = Column(Uuid, ForeignKey('translation_project.id', ondelete='CASCADE'), primary_key=True)
    statement_required = Column(Boolean)
    quotation_data = Column(JSON)
    quotation_revision = Column(Integer, nullable=False, default=0)
    updated_by = Column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=business_now, onupdate=business_now)


def ready(db):
    key = 'translation_project_documents_ready'
    if key not in db.info:
        db.info[key] = inspect(db.connection()).has_table(TranslationProjectDocuments.__tablename__)
    return db.info[key]


def required_expression(db):
    """SQL 筛选与表单默认值一致：显式值优先，个人客户默认不需。"""
    from sqlalchemy import select,func,and_,or_,literal,case
    from models import TranslationProject,SubClient
    from customer_statement_defaults import CustomerStatementDefault
    from translation_customer_type import ClientCustomerType,ready as types_ready
    explicit=select(TranslationProjectDocuments.statement_required).where(TranslationProjectDocuments.project_id==TranslationProject.id).correlate(TranslationProject).scalar_subquery() if ready(db) else literal(None)
    inherited=literal(True)
    if types_ready(db):
        customer_type=select(ClientCustomerType.customer_type).where(or_(and_(TranslationProject.sub_client_id.is_(None),ClientCustomerType.client_id==TranslationProject.client_id),ClientCustomerType.sub_client_id==TranslationProject.sub_client_id)).correlate(TranslationProject).scalar_subquery()
        inherited=func.coalesce(customer_type!='个人客户',True)
    parent=select(SubClient.parent_client_id).where(SubClient.id==TranslationProject.sub_client_id).correlate(TranslationProject).scalar_subquery()
    choice=select(CustomerStatementDefault.choice).where(CustomerStatementDefault.client_id==func.coalesce(TranslationProject.client_id,parent)).correlate(TranslationProject).scalar_subquery()
    customer_default=case((choice=='required',True),(choice=='not_required',False),else_=inherited)
    return func.coalesce(explicit,and_(customer_default,~full_payment_expression(db)))


def full_payment_expression(db):
    from sqlalchemy import select,func,and_,or_,literal
    from models import TranslationProject
    from translation_payment_confirmation import TranslationPaymentConfirmation,ready as payments_ready
    if not payments_ready(db):return literal(False)
    model=TranslationPaymentConfirmation
    encoded=func.replace(model.payment_option,' ','')
    full=or_(model.payment_option=='full',encoded.like('%"type":"full"%'),and_(encoded.like('%"source":"details"%'),encoded.like('%"match_status":"matched"%')))
    return func.coalesce(select(and_(model.is_paid.is_(True),full)).where(model.project_id==TranslationProject.id).correlate(TranslationProject).scalar_subquery(),False)


def full_payment(value):
    return bool(value and value.get('is_paid') and (value.get('payment_option')=='full' or value.get('full_payment_source')=='details' and value.get('full_match_status')=='matched'))


def attach(db, projects):
    if not projects:
        return
    from translation_payment_confirmation import attach as attach_payments
    attach_payments(db,projects)
    from customer_statement_defaults import choices_for_projects
    defaults=choices_for_projects(db,projects)
    rows = {row.project_id: row for row in db.query(TranslationProjectDocuments).filter(
        TranslationProjectDocuments.project_id.in_([row.id for row in projects])).all()} if ready(db) else {}
    for project in projects:
        row = rows.get(project.id)
        project.statement_required_explicit=bool(row and row.statement_required is not None)
        choice=defaults.get(project.id,'unknown')
        inherited=choice=='required' if choice!='unknown' else getattr(project,'customer_type',None)!='个人客户'
        project.statement_required = row.statement_required if project.statement_required_explicit else inherited and not full_payment(getattr(project,'payment_confirmation',None))
        project.quotation_draft = quotation_value(row)
        project.document_notes = document_notes(row)
        project.invoice_data=(row.quotation_data or {}).get('_invoice',{}) if row else {}
        project.order_pricing_modes = (row.quotation_data or {}).get('_order_pricing_modes', {}) if row else {}


def save(db, project, *, statement_required=None, quotation_draft=None, document_notes=None, actor_id=None):
    if statement_required is None and quotation_draft is None and document_notes is None:
        return
    if not ready(db):
        raise HTTPException(503, '项目单据存储尚未初始化')
    row = db.get(TranslationProjectDocuments, project.id)
    if row is None:
        row = TranslationProjectDocuments(project_id=project.id, quotation_revision=0)
        db.add(row)
    if statement_required is not None:
        row.statement_required = statement_required
    stored=dict(row.quotation_data or {})
    if quotation_draft is not None:
        stored={**quotation_draft.model_dump(mode='json'),**{key:value for key,value in stored.items() if key.startswith('_')}}
        row.quotation_revision += 1
    if document_notes is not None:
        stored['_document_notes']=document_notes.model_dump(mode='json')
        project.document_notes=document_notes.model_dump(mode='json')
    row.quotation_data=stored or None
    row.updated_by = actor_id
    row.updated_at = business_now()


def order_pricing_modes(db, project):
    if not hasattr(project, 'order_pricing_modes'):
        row = db.get(TranslationProjectDocuments, project.id) if db and ready(db) else None
        project.order_pricing_modes = (row.quotation_data or {}).get('_order_pricing_modes', {}) if row else {}
    return project.order_pricing_modes


def save_order_pricing_mode(db, project, order_id, mode, actor_id):
    if not ready(db):
        raise HTTPException(503, '项目单据存储尚未初始化')
    row = db.get(TranslationProjectDocuments, project.id)
    if row is None:
        row = TranslationProjectDocuments(project_id=project.id, quotation_revision=0)
        db.add(row)
    stored = dict(row.quotation_data or {})
    modes = dict(stored.get('_order_pricing_modes', {}))
    modes[str(order_id)] = mode
    row.quotation_data = {**stored, '_order_pricing_modes': modes}
    row.updated_by = actor_id
    row.updated_at = business_now()
    project.order_pricing_modes = modes


def quotation(db, project):
    if not ready(db):
        raise HTTPException(503, '报价单存储尚未初始化')
    row = db.get(TranslationProjectDocuments, project.id)
    if quotation_value(row):
        draft = QuotationDraft.model_validate(quotation_value(row))
    else:
        draft = QuotationDraft(client_name=getattr(project, 'sub_client_name', None) or getattr(project, 'client_name', None) or '')
        draft.items = [QuotationLine(description=project.source_file_name or project.project_name or '', language_pair=project.language_pair or '')]
    return dict(project_id=project.id, order_no=project.order_no, revision=row.quotation_revision if row else 0, document=draft.model_dump(mode='json'))
