"""笔译项目单据要求与报价内容；对账单内容继续使用既有工作区。"""
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, Uuid, inspect
from fastapi import HTTPException
from models import Base
from annotation_progress_time import business_now

PaymentMethod = Literal['individual', 'statement', 'monthly', 'sub_client', 'special']
SettlementMode = Literal['individual', 'monthly', 'sub_client', 'special']
StatementScope = Literal['standard', 'special']
GROUPED_SETTLEMENT_MODES = ('monthly', 'sub_client')


def matches_statement_scope(project, scope):
    return scope is None or (payment_method(project) == 'special') == (scope == 'special')


def payment_method(project):
    recorded = getattr(project, 'recorded_payment_method', None)
    if recorded == 'special':
        return 'special'
    if getattr(project, 'sub_client_id', None):
        return 'sub_client'
    for field in ('recorded_payment_method', 'customer_payment_method'):
        method = getattr(project, field, None)
        if method in ('individual', 'monthly', 'statement', 'special'):
            return 'monthly' if method == 'statement' else method
    return 'monthly' if getattr(project, 'has_monthly_payment_peers', False) else 'individual'


def payment_summary_method(project):
    mode = payment_method(project)
    return 'statement' if mode == 'monthly' and project.statement_required else mode


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


def billing_period_month_expression(db):
    from sqlalchemy import literal, select
    from models import TranslationProject

    if not ready(db):
        return literal(None)
    return select(TranslationProjectDocuments.quotation_data['_billing_period']['month'].as_string()).where(
        TranslationProjectDocuments.project_id == TranslationProject.id,
    ).correlate(TranslationProject).scalar_subquery()


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


def statement_customer_ids(db, *, required_only=True):
    from sqlalchemy import func, select
    from models import TranslationProject, SubClient
    client_id = func.coalesce(TranslationProject.client_id, SubClient.parent_client_id)
    candidates = (db.query(client_id.label('client_id'))
                  .outerjoin(SubClient, SubClient.id == TranslationProject.sub_client_id)
                  .filter(TranslationProject.annotation_migrated_at.is_(None), client_id.is_not(None)))
    if required_only:
        candidates = candidates.filter(required_expression(db).is_(True))
    return select(candidates.subquery().c.client_id)


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
    from customer_statement_defaults import defaults_for_projects
    defaults=defaults_for_projects(db,projects)
    rows = {row.project_id: row for row in db.query(TranslationProjectDocuments).filter(
        TranslationProjectDocuments.project_id.in_([row.id for row in projects])).all()} if ready(db) else {}
    for project in projects:
        row = rows.get(project.id)
        project.statement_required_explicit=bool(row and row.statement_required is not None)
        choice, finance_default = defaults[project.id]
        inherited=choice=='required' if choice!='unknown' else getattr(project,'customer_type',None)!='个人客户'
        fully_paid=full_payment(getattr(project,'payment_confirmation',None))
        project.statement_required = row.statement_required if project.statement_required_explicit else inherited and not fully_paid
        project.recorded_payment_method = (row.quotation_data or {}).get('_payment_method') if row else None
        project.customer_payment_method = getattr(finance_default, 'payment_method', None)
        stored = (row.quotation_data or {}) if row else {}
        quotation_default = getattr(finance_default, 'quotation_required', None)
        invoice_default = getattr(finance_default, 'invoice_required', None)
        quotation_explicit = '_quotation_required' in stored or bool(project.quotation_required)
        project.effective_quotation_required = bool(project.quotation_required if quotation_explicit else quotation_default)
        project.effective_invoice_required = stored.get('_invoice_required', invoice_default)
        project.order_invoice_requirements = stored.get('_order_invoice_requirements', {})
        project.order_statement_requirements = stored.get('_order_statement_requirements', {})
        project.billing_period = stored.get('_billing_period') or {}
        project.customer_document_defaults = {
            'statement_required': None if choice == 'unknown' else choice == 'required',
            'quotation_required': quotation_default, 'invoice_required': invoice_default,
            'payment_method': project.customer_payment_method,
        }
        project.customer_document_sources = {
            'statement_required': not project.statement_required_explicit and choice != 'unknown' and (not fully_paid or choice=='not_required'),
            'quotation_required': not quotation_explicit and quotation_default is not None,
            'invoice_required': '_invoice_required' not in stored and invoice_default is not None,
            'payment_method': not project.recorded_payment_method and project.customer_payment_method is not None,
        }
        project.quotation_draft = quotation_value(row)
        project.document_notes = document_notes(row)
        project.invoice_data=(row.quotation_data or {}).get('_invoice',{}) if row else {}
        project.order_pricing_modes = (row.quotation_data or {}).get('_order_pricing_modes', {}) if row else {}
        project.order_total_adjustments = stored.get('_order_total_adjustments', {})
        project.document_consistency_review = stored.get('_document_consistency_review')
        project.cleared_price_orders = set(stored.get('_cleared_price_orders', []))


def set_price_default_disabled(db, project, order_id, disabled, actor_id):
    cleared = getattr(project, 'cleared_price_orders', set()).copy()
    if (order_id in cleared) == disabled:
        return
    row = db.get(TranslationProjectDocuments, project.id)
    if row is None:
        row = TranslationProjectDocuments(project_id=project.id, quotation_revision=0)
        db.add(row)
    if disabled:
        cleared.add(order_id)
    else:
        cleared.discard(order_id)
    row.quotation_data = {**(row.quotation_data or {}), '_cleared_price_orders': sorted(cleared)}
    row.updated_by = actor_id
    row.updated_at = business_now()
    project.cleared_price_orders = cleared


def save_consistency_review(db, project, review, actor_id):
    if not ready(db):
        raise HTTPException(503, '项目单据存储尚未初始化')
    row = db.get(TranslationProjectDocuments, project.id)
    if row is None:
        row = TranslationProjectDocuments(project_id=project.id, quotation_revision=0)
        db.add(row)
    stored = dict(row.quotation_data or {})
    if review:
        stored['_document_consistency_review'] = review
    else:
        stored.pop('_document_consistency_review', None)
    row.quotation_data = stored or None
    row.updated_by = actor_id
    row.updated_at = business_now()
    project.document_consistency_review = review


def save(db, project, *, statement_required=None, quotation_draft=None, document_notes=None, payment_method=None, quotation_required=None, invoice_required=None, document_order_id=None, actor_id=None):
    if all(value is None for value in (statement_required, quotation_draft, document_notes, payment_method, quotation_required, invoice_required)):
        return
    if not ready(db):
        raise HTTPException(503, '项目单据存储尚未初始化')
    row = db.get(TranslationProjectDocuments, project.id)
    if row is None:
        row = TranslationProjectDocuments(project_id=project.id, quotation_revision=0)
        db.add(row)
    is_child = document_order_id is not None and document_order_id != project.id
    if statement_required is not None and not is_child:
        row.statement_required = project.statement_required = statement_required
        project.statement_required_explicit = True
    stored=dict(row.quotation_data or {})
    if statement_required is not None and is_child:
        overrides = dict(stored.get('_order_statement_requirements', {}))
        overrides[str(document_order_id)] = statement_required
        stored['_order_statement_requirements'] = project.order_statement_requirements = overrides
    if quotation_required is not None:
        stored['_quotation_required'] = quotation_required
        project.quotation_required = project.effective_quotation_required = quotation_required
    if any(value is not None for value in (statement_required, quotation_required, invoice_required, payment_method)):
        sources = getattr(project, 'customer_document_sources', {}).copy()
        for field,value in (('statement_required',statement_required),('quotation_required',quotation_required),
                            ('invoice_required',invoice_required),('payment_method',payment_method)):
            if value is not None:
                sources[field] = False
        project.customer_document_sources = sources
    if invoice_required is not None:
        if is_child:
            overrides = dict(stored.get('_order_invoice_requirements', {}))
            overrides[str(document_order_id)] = invoice_required
            stored['_order_invoice_requirements'] = project.order_invoice_requirements = overrides
        else:
            stored['_invoice_required'] = invoice_required
            project.effective_invoice_required = invoice_required
    if quotation_draft is not None:
        stored={**quotation_draft.model_dump(mode='json'),**{key:value for key,value in stored.items() if key.startswith('_')}}
        row.quotation_revision += 1
    if document_notes is not None:
        stored['_document_notes']=document_notes.model_dump(mode='json')
        project.document_notes=document_notes.model_dump(mode='json')
    if payment_method is not None:
        stored['_payment_method'] = payment_method
        project.recorded_payment_method = payment_method
    row.quotation_data=stored or None
    row.updated_by = actor_id
    row.updated_at = business_now()


def apply_customer_documents(db, client_id, changes, actor_id):
    from sqlalchemy import func
    from models import TranslationProject, SubClient

    if not ready(db):
        return
    projects = db.query(TranslationProject).outerjoin(SubClient,SubClient.id==TranslationProject.sub_client_id).filter(
        func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)==client_id,
        TranslationProject.annotation_migrated_at.is_(None),
    ).order_by(TranslationProject.id).with_for_update(of=TranslationProject).all()
    rows = {row.project_id:row for row in db.query(TranslationProjectDocuments).filter(
        TranslationProjectDocuments.project_id.in_([project.id for project in projects]))}
    moment = business_now()
    for project in projects:
        row = rows.get(project.id)
        stored = dict(row.quotation_data or {}) if row else {}
        if 'quotation_required' in changes:
            project.quotation_required = False  # Explicit values move back to the customer default.
        for field in ('quotation_required','invoice_required','payment_method'):
            if field in changes:
                stored.pop('_'+field,None)
        if row:
            if 'statement_default' in changes:
                row.statement_required=None
            row.quotation_data=stored or None
            row.updated_at=moment
            row.updated_by=actor_id
        project.updated_at=moment.replace(tzinfo=None)


def load_order_pricing_modes(db, projects):
    pending = {project.id: project for project in projects if not hasattr(project, 'order_total_adjustments')}
    if not pending:
        return
    rows = {}
    if ready(db):
        rows = dict(db.query(TranslationProjectDocuments.project_id, TranslationProjectDocuments.quotation_data)
                    .filter(TranslationProjectDocuments.project_id.in_(pending)).all())
    for project_id, project in pending.items():
        stored = rows.get(project_id) or {}
        project.order_pricing_modes = stored.get('_order_pricing_modes', {})
        project.order_total_adjustments = stored.get('_order_total_adjustments', {})


def order_pricing_modes(db, project):
    if db is not None:
        load_order_pricing_modes(db, [project])
    return getattr(project, 'order_pricing_modes', {})


def save_order_total_adjustment(db, project, order_id, changes, currency, actor_id):
    if not ready(db):
        raise HTTPException(503, '项目单据存储尚未初始化')
    row = db.get(TranslationProjectDocuments, project.id)
    if row is None:
        row = TranslationProjectDocuments(project_id=project.id, quotation_revision=0)
        db.add(row)
    stored = dict(row.quotation_data or {})
    adjustments = dict(stored.get('_order_total_adjustments', {}))
    entry = {**adjustments.get(order_id, {}), 'currency': currency}
    for key, value in changes.items():
        if value is None:
            entry.pop(key, None)
        else:
            entry[key] = value if key.endswith('_discount') else format(value, '.2f')
    if len(entry) > 1:
        adjustments[order_id] = entry
    else:
        adjustments.pop(order_id, None)
    row.quotation_data = {**stored, '_order_total_adjustments': adjustments}
    row.updated_by = actor_id
    row.updated_at = business_now()
    project.order_total_adjustments = adjustments


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
