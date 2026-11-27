"""客户计价及订单树汇总；复用既有收费表，不更改数据库结构。"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import re
from hashlib import sha256
import json
from uuid import UUID, uuid4
from typing import Literal, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import func, inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, joinedload, selectinload, object_session
from database import get_db
from models import TranslationProject, TranslationSubOrder, TranslationSubOrderChargeItem, Client, SubClient, AppUser
from routers.auth import get_current_user, require_permission, require_module_access, require_any_permission
from annotation_progress_time import business_now, business_datetime
import crud
import customer_translation_rates as rates
import translation_finance_audit as audit
import translation_quantity_basis as quantity_basis
import translation_rate_matching as rate_matching
import translation_payment_confirmation as confirmations
import translation_finance_notes as finance_notes
import translation_billing_tax_mode as billing_tax
import translation_special_settlement as special_settlement
import sub_client_finance
from translation_payment_confirmation import PaymentConfirmationWrite
from translation_payment_service import ProjectPayment
from permission_service import user_has_permission
from statement_customer_groups import CustomerGroupMove
from customer_statement_progress import Progress,ProgressWrite

METRICS = {'characters_no_spaces','words','foreign_words','cjk_chars_korean_words','documents','pages'}


from translation_document_requirements import GROUPED_SETTLEMENT_MODES,QuotationDraft,DocumentNotes,PaymentMethod,SettlementMode,StatementScope,matches_statement_scope,payment_method,order_pricing_modes,save_order_pricing_mode,save_order_total_adjustment
from translation_project_invoices import InvoiceWrite, InvoiceCustomerSentWrite

class StatementSyncScope(BaseModel):
    client_id: UUID
    billing_month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')


class StatementCustomerSync(BaseModel):
    client_id: UUID
    revision: int = Field(ge=0)
    sync_document_requirements: bool = False
    document_fields: list[Literal['quotation_required','invoice_required']] | None = Field(default=None,max_length=2)


class DocumentConsistencyReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    snapshot: list[tuple[str, bool, bool, bool | None, str | None]]
    reason: str = Field(default='', max_length=2000)


class OrderTotalAdjustment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    excl_tax: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    incl_tax: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    excl_discount: int | None = Field(default=None, ge=1, le=99)
    incl_discount: int | None = Field(default=None, ge=1, le=99)


class PriceWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    record_initial_finance: bool = False
    clear_finance: bool = False
    payment_confirmation: PaymentConfirmationWrite | None = None
    payment_draft: list[ProjectPayment] | None = Field(default=None,max_length=100)
    payment_version: str | None = None
    payment_method: SettlementMode | None = None
    billing_tax_mode: Literal['excl_tax','incl_tax'] | None = None
    quotation_required: bool | None = None
    invoice_required: bool | None = None
    statement_required: bool | None = None
    statement_sync: StatementSyncScope | None = None
    statement_customer_sync: StatementCustomerSync | None = None
    quotation_draft: QuotationDraft | None = None
    document_notes: DocumentNotes | None = None
    document_consistency_review: DocumentConsistencyReview | None = None
    documents_only: bool = False
    version: str
    order_id: UUID
    pricing_mode: Literal['metric','fixed'] = 'metric'
    order_pricing_mode: Literal['aggregate','metric','fixed'] | None = None
    amount: Decimal | None = Field(default=None,ge=0, max_digits=14, decimal_places=4)
    currency: str = Field(default='CNY', pattern=r'^[A-Z]{3}$')
    metric: str = 'characters_no_spaces'
    unit_size: Decimal = Field(default=Decimal('1'), gt=0, max_digits=14, decimal_places=4)
    adjusted_total: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    adjusted_total_incl_tax: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    total_adjustment: OrderTotalAdjustment | None = None
    explanation: str = Field(default='', max_length=5000)
    customer_explanation:str|None=Field(default=None,max_length=5000)
    billing_month: str | None = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    prices: list[rates.RateInput] | None = Field(default=None,min_length=1,max_length=100)
    update_library: bool = False
    sync_confirmed: bool = False
    library_version: str | None = None


def primary(owner):
    rows = sorted(owner.customer_charge_items or [], key=lambda row: row.sequence_no or 0)
    return next((row for row in rows if row.item_name == '翻译费' and row.pricing_mode == 'metric'), next((row for row in rows if row.pricing_mode == 'metric'), next((row for row in rows if row.pricing_mode=='fixed'),None)))


def signature(row):
    if row is None:
        return None
    return (rates.order_unit_amount(row),
            row.currency or 'CNY', row.metric_type, Decimal(str(row.unit_size)).normalize() if row.unit_size is not None else None)


def hierarchy(project):
    owners = [project, *sorted(project.sub_orders or [], key=lambda row: row.sub_order_no)]
    numbers = {str(project.id): project.order_no, **{str(row.id): row.sub_order_no for row in owners[1:]}}
    by_number = {number: key for key, number in numbers.items()}
    parents = {str(row.id): by_number.get(row.sub_order_no.rsplit('.', 1)[0], str(project.id)) for row in owners[1:]}
    return owners, numbers, parents


def version(project):
    owners, numbers, parents = hierarchy(project)
    fields = []
    fields.append(getattr(project,'document_notes',{}))
    fields.append(getattr(project, 'document_consistency_review', None))
    fields.append(getattr(project, 'effective_invoice_required', None))
    fields.append(getattr(project, 'order_invoice_requirements', {}))
    fields.append(getattr(project, 'order_statement_requirements', {}))
    fields.append(getattr(project, 'billing_period', {}))
    fields.append(getattr(project, 'effective_quotation_required', None))
    fields.append(getattr(project, 'recorded_payment_method', None))
    fields.append(order_pricing_modes(object_session(project), project))
    fields.append(getattr(project,'order_total_adjustments',{}))
    fields.append([bool(getattr(project,'quotation_required',False)),bool(getattr(project,'statement_required',True)),getattr(project,'quotation_draft',None)])
    for owner in owners:
        fields.append([str(owner.id), numbers[str(owner.id)], parents.get(str(owner.id)), str(owner.updated_at),
                       owner.word_count_matrix,
                       [[str(row.id), str(signature(row)),str(row.unit_price_excl_tax),str(row.unit_price_incl_tax),str(Decimal(str(row.total_excl_tax)).normalize()) if row.total_excl_tax is not None else None,str(Decimal(str(row.total_incl_tax)).normalize()) if row.total_incl_tax is not None else None,row.billing_month,row.remarks,str(row.updated_at)] for row in owner.customer_charge_items]])
    db=object_session(project)
    if db:
        if project.sub_client_id:
            preference=sub_client_finance.load(db,{project.sub_client_id}).get(project.sub_client_id)
            if preference:
                fields.append(('sub_client_finance',str(project.sub_client_id),preference.revision))
        fields.append(billing_tax.modes(db,project.id))
        fields.append([rates.order_rates(db,owner,owner.language_pair or project.language_pair) for owner in owners])
        fields.append([(key,row.internal_note,row.customer_note,row.revision) for key,row in sorted(finance_notes.rows(db,project.id).items())])
    return sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()


def order_billing_month(order_no):
    match=re.match(r'^TP-(\d{8}|\d{6})-',str(order_no or '').strip().upper())
    if not match:return None
    digits=match[1]
    year,month=(digits[:4],digits[4:6]) if len(digits)==8 else ('20'+digits[:2],digits[2:4])
    return f'{year}-{month}' if 1<=int(month)<=12 else None


def effective_billing_month(project,owner=None):
    assigned = getattr(project, 'billing_period', {}).get('month')
    if assigned:
        return assigned
    month=order_billing_month(project.order_no)
    if month:return month
    row=primary(owner or project)
    if row and row.billing_month:return row.billing_month
    row=primary(project)
    return row.billing_month if row else None


def settlement_period_numbers(db, orders):
    """Use the current numbered board, including orders assigned before the board was split."""
    from customer_statement_workspace import StatementWorkspace
    from statement_document_status import months as statement_months

    client_ids = {client for _, client, _, _ in orders if client}
    linked_periods = {}
    if not client_ids:
        return {}
    workspaces = {}
    if inspect(db.connection()).has_table(StatementWorkspace.__tablename__):
        payload=StatementWorkspace.payload
        for client,boards,tasks,parties,settings in db.query(StatementWorkspace.client_id,
                payload['boards'],payload['tasks'],payload[sub_client_finance.PERIOD_PARTIES],
                payload[sub_client_finance.DOCUMENT_SETTINGS]).filter(StatementWorkspace.client_id.in_(client_ids)):
            workspaces[client]={'boards':boards or [],'tasks':tasks or {},
                sub_client_finance.PERIOD_PARTIES:parties or {},sub_client_finance.DOCUMENT_SETTINGS:settings or {}}
    db.info.setdefault('settlement_workspace_payloads', {}).update(workspaces)
    boards_by_client = {}
    for client, payload in workspaces.items():
        boards = {board['id']: board for board in payload.get('boards', []) if board.get('period_number') and board.get('status')!='void'}
        board_months={key:set(statement_months(payload,board)) for key,board in boards.items()}
        boards_by_client[client] = boards
        for task in payload.get('tasks', {}).values():
            board = boards.get(task.get('board_id'))
            if not board or task['month'] not in board_months[board['id']]:
                continue
            for line in task['rows']:
                linked_periods.setdefault((client, line['root_id'], task['month']), set()).add(board['period_number'])
    numbers = {}
    for order_id, client, month, assignment in orders:
        number = assignment.get('number') if assignment.get('month') == month else None
        if assignment.get('month') == month and assignment.get('board_id'):
            board = boards_by_client.get(client, {}).get(assignment['board_id'], {})
            if board and month in statement_months(workspaces[client],board):
                number = board.get('period_number')
        if not number and not assignment.get('board_id'):
            linked = linked_periods.get((client, str(order_id), month), set())
            number = next(iter(linked)) if len(linked) == 1 else None
            if len(linked) > 1:
                number = str(order_id)
        numbers[order_id] = number
    return numbers


def settlement_candidates(db, scopes):
    from customer_statement_defaults import CustomerTranslationFinanceDefault, finance_defaults_ready
    from translation_payment_filters import payment_record_condition
    from translation_document_requirements import TranslationProjectDocuments, ready as documents_ready
    from sqlalchemy import literal
    customer = func.coalesce(TranslationProject.client_id, SubClient.parent_client_id)
    query = db.query(TranslationProject.id, customer, TranslationProject.order_no,payment_record_condition(db),
                     TranslationProject.sub_client_id).outerjoin(
        SubClient, SubClient.id == TranslationProject.sub_client_id,
    ).filter(TranslationProject.annotation_migrated_at.is_(None), customer.in_({client for client, _ in scopes}))
    if documents_ready(db):
        query = query.outerjoin(TranslationProjectDocuments, TranslationProjectDocuments.project_id == TranslationProject.id).add_columns(TranslationProjectDocuments.quotation_data)
    else:
        query = query.add_columns(literal(None))
    if finance_defaults_ready(db):
        query=query.outerjoin(CustomerTranslationFinanceDefault,CustomerTranslationFinanceDefault.client_id==customer).add_columns(CustomerTranslationFinanceDefault.payment_method)
    else:
        query=query.add_columns(literal(None))
    candidates = crud._apply_translation_project_filters(query, field_filters={
        'finance_billing_month': {'value': sorted({month for _, month in scopes})},
    })
    records = []
    settings={}
    explicit_modes = {}
    for order_id, client, number, paid, sub_client_id, documents, default_mode in candidates:
        documents=documents or {}
        assignment = (documents or {}).get('_billing_period') or {}
        month=assignment.get('month') or order_billing_month(number)
        if (client,month) not in scopes:
            continue
        records.append((order_id, client, month, assignment))
        recorded = documents.get('_payment_method')
        explicit_modes[order_id] = recorded
        mode = recorded or ('sub_client' if sub_client_id else default_mode)
        settings[order_id]=(bool(paid),mode,documents.get('_paid_monthly_members',[]),sub_client_id)
    periods = settlement_period_numbers(db, records)
    explicit_monthly_groups = {(client,month,periods.get(order_id)) for order_id,client,month,_ in records
                               if explicit_modes[order_id] in ('monthly','statement')}
    for order_id,client,month,_ in records:
        paid,mode,members,child_id = settings[order_id]
        if not paid and not explicit_modes[order_id] and (client,month,periods.get(order_id)) in explicit_monthly_groups:
            settings[order_id] = (paid,'monthly',members,child_id)
    return [(order_id,client,month,periods.get(order_id),*settings[order_id]) for order_id,client,month,_ in records]


def attach_monthly_payment_peers(db, projects):
    scopes = {}
    for project in projects:
        project.has_monthly_payment_peers = False
        project.in_explicit_monthly_group = False
        project.settlement_period_number = None
        project.settlement_party = 'sub_client' if project.sub_client_id else 'client'
        client_id,month = statement_client_id(project),effective_billing_month(project)
        if client_id and month:
            scopes.setdefault((client_id, month), []).append(project)
    if not scopes:
        return
    candidates=settlement_candidates(db,scopes)
    paid_members=set()
    paid_groups=set()
    for uid,client,month,period,paid,mode,members,_ in candidates:
        if paid and mode not in ('individual','sub_client','special'):
            paid_groups.add((client,month,period))
            paid_members.update((client,month,period,member) for member in members)
    unpaid_groups={}
    for uid,client,month,period,paid,mode,_,_ in candidates:
        if not paid and mode not in ('individual','sub_client','special'):
            unpaid_groups.setdefault((client,month,period),[]).append(str(uid))
    by_id={row[0]:row for row in candidates}
    for scope, orders in scopes.items():
        for project in orders:
            candidate=by_id.get(project.id)
            if not candidate:
                continue
            _,client,month,period,paid,mode,_,_=candidate
            project.settlement_period_number=period
            project.in_explicit_monthly_group = mode == 'monthly' and not getattr(project,'recorded_payment_method',None)
            if project.sub_client_id:
                workspace = db.info.get('settlement_workspace_payloads', {}).get(client)
                project.settlement_party = sub_client_finance.period_party(workspace, project.sub_client_id, month, period)
            group=(client,month,period)
            project.unpaid_monthly_member_ids=unpaid_groups.get(group,[])
            project.has_monthly_payment_peers=(*group,str(project.id)) in paid_members or (
                group not in paid_groups and not paid and len(project.unpaid_monthly_member_ids)>1
            )


def preserve_paid_monthly_members(db,project):
    from translation_document_requirements import TranslationProjectDocuments,attach,ready
    if not ready(db):
        return
    attach(db,[project])
    attach_monthly_payment_peers(db,[project])
    members=getattr(project,'unpaid_monthly_member_ids',[])
    if payment_method(project)!='monthly' or str(project.id) not in members or len(members)<2:
        return
    document=db.get(TranslationProjectDocuments,project.id)
    if document is None:
        document=TranslationProjectDocuments(project_id=project.id,quotation_revision=0)
        db.add(document)
    document.quotation_data={**(document.quotation_data or {}),'_paid_monthly_members':members}
    db.flush()


def statement_client_id(project):
    return project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)


def project_statement_client_id(db, project_id):
    return db.query(func.coalesce(TranslationProject.client_id, SubClient.parent_client_id)).outerjoin(
        SubClient, SubClient.id == TranslationProject.sub_client_id).filter(TranslationProject.id == project_id).scalar()


def statement_month_projects(db, client_id, month):
    query = db.query(TranslationProject).outerjoin(Client, TranslationProject.client_id == Client.id).outerjoin(
        SubClient, SubClient.id == TranslationProject.sub_client_id).filter(
        TranslationProject.annotation_migrated_at.is_(None),
        func.coalesce(TranslationProject.client_id, SubClient.parent_client_id) == client_id)
    return crud._apply_translation_project_filters(query, field_filters={'finance_billing_month': {'value': month}})


def settlement_group_key(project):
    method = payment_method(project)
    return (statement_client_id(project), effective_billing_month(project),
            getattr(project, 'settlement_period_number', None), method,
            project.sub_client_id if method == 'sub_client' else None)


def monthly_tax_projects(db, project):
    client_id, month = statement_client_id(project), effective_billing_month(project)
    if payment_method(project) not in GROUPED_SETTLEMENT_MODES or not client_id or not month:
        return [project]
    key = (client_id, month)
    cache = db.info.setdefault('translation_monthly_tax_projects', {})
    if key not in cache:
        from translation_document_requirements import attach as attach_documents
        candidates = statement_month_projects(db, client_id, month).options(
            joinedload(TranslationProject.client),
            joinedload(TranslationProject.sub_client),
            selectinload(TranslationProject.customer_charge_items),
            selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.customer_charge_items),
        ).order_by(TranslationProject.id).all()
        attach_documents(db, [candidate for candidate in candidates if candidate.id != project.id])
        load_charge_metadata(db, candidates)
        attach_monthly_payment_peers(db, candidates)
        cache[key] = candidates
    group = settlement_group_key(project)
    return [candidate for candidate in cache[key] if settlement_group_key(candidate) == group]


def preload_monthly_tax_projects(db, projects):
    """列表一次读取所有涉及账期的结算同组订单，避免每个客户/月份再查一遍。"""
    scopes = {(statement_client_id(project), effective_billing_month(project)) for project in projects
              if payment_method(project) in GROUPED_SETTLEMENT_MODES}
    cache = db.info.setdefault('translation_monthly_tax_projects', {})
    scopes = {scope for scope in scopes if all(scope) and scope not in cache}
    if not scopes:
        return
    customer = func.coalesce(TranslationProject.client_id, SubClient.parent_client_id)
    query = db.query(TranslationProject).outerjoin(SubClient, SubClient.id == TranslationProject.sub_client_id).filter(
        TranslationProject.annotation_migrated_at.is_(None), customer.in_({client for client, _ in scopes}))
    query = crud._apply_translation_project_filters(query, field_filters={
        'finance_billing_month': {'value': sorted({month for _, month in scopes})},
    })
    candidates = query.options(
        joinedload(TranslationProject.client), joinedload(TranslationProject.sub_client),
        selectinload(TranslationProject.customer_charge_items),
        selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.customer_charge_items),
    ).order_by(TranslationProject.id).all()
    from translation_document_requirements import attach as attach_documents
    original_ids = {project.id for project in projects}
    attach_documents(db, [project for project in candidates if project.id not in original_ids])
    candidates = [project for project in candidates
                  if (statement_client_id(project), effective_billing_month(project)) in scopes]
    attach_monthly_payment_peers(db, candidates)
    load_charge_metadata(db, candidates)
    from project_client_manager import attach as attach_managers
    attach_managers(db, 'translation', candidates)
    for project in candidates:
        crud._attach_project_client_fields(project)
    crud._attach_word_count_matrices(db, projects=candidates)
    attach_customer_price_defaults(db, candidates)
    db.info.setdefault('translation_monthly_tax_preloaded', set()).update(project.id for project in candidates)
    grouped = {scope: [] for scope in scopes}
    for project in candidates:
        grouped[(statement_client_id(project), effective_billing_month(project))].append(project)
    cache.update(grouped)


def latest_monthly_tax_mode(db, peers):
    if not billing_tax.ready(db):
        return None
    ids = tuple(sorted(peer.id for peer in peers))
    cache = db.info.setdefault('translation_monthly_tax_modes', {})
    if ids in cache:
        return cache[ids]
    model = billing_tax.TranslationBillingTaxMode
    latest = db.query(model.mode).filter(model.order_id.in_(ids)).order_by(
        model.updated_at.desc(), model.order_id
    ).first()
    cache[ids] = latest[0] if latest else None
    return cache[ids]


def unified_tax_mode(db, project, node, stored, fallback):
    method = payment_method(project)
    if project.sub_client_id and getattr(project, 'settlement_party', None) == 'client':
        return fallback
    preference = (sub_client_finance.load(db, {project.sub_client_id}).get(project.sub_client_id)
                  if db is not None and project.sub_client_id else None)
    if preference and preference.tax_mode:
        return preference.tax_mode
    if method == 'special':
        return None
    peers = monthly_tax_projects(db, project) if db and method in GROUPED_SETTLEMENT_MODES else [project]
    choices = set(billing_tax.available(node))
    if len(peers) > 1:
        key = ('available', tuple(sorted((peer.id, peer.updated_at) for peer in peers)))
        cache = db.info.setdefault('translation_monthly_tax_modes', {})
        if key not in cache:
            others = [peer for peer in peers if peer.id != project.id]
            preloaded = db.info.get('translation_monthly_tax_preloaded', set())
            pending = [peer for peer in others if peer.id not in preloaded]
            for peer in pending:
                crud._attach_project_client_fields(peer)
            if pending:
                crud._attach_word_count_matrices(db, projects=pending)
                attach_customer_price_defaults(db, pending)
            common = choices or {'incl_tax', 'excl_tax'}
            for peer in others:
                peer_node = tree(peer, summary_only=True, include_billing_tax_mode=False,
                                 include_version=False)['item']
                peer_choices = billing_tax.available(peer_node)
                if peer_choices:
                    common.intersection_update(peer_choices)
                    if not common:
                        break
            cache[key] = common
        choices = cache[key]
        if len(choices) == 1:
            return next(iter(choices))
        return latest_monthly_tax_mode(db, peers) or fallback
    if len(choices) == 1:
        return next(iter(choices))
    return billing_tax.order_mode(node, stored, fallback) or (
        fallback if node.get('children') else None
    )


def save_settlement_tax(db, user, project, owner, mode):
    if payment_method(project) == 'special':
        billing_tax.save(db, user, project, owner, mode)
        return []
    if payment_method(project) == 'sub_client':
        if getattr(project, 'settlement_party', None) == 'client':
            return []
        if mode is not None:
            sub_client_finance.write(db, project.sub_client_id, {'tax_mode':mode}, user.id)
        return []
    if mode is None:
        return []
    peers = monthly_tax_projects(db, project)
    if len(peers) > 1:
        ids = [peer.id for peer in peers]
        db.query(TranslationProject.id).filter(TranslationProject.id.in_(ids)).order_by(
            TranslationProject.id
        ).with_for_update().all()
    others = [peer for peer in peers if peer.id != project.id]
    for peer in others:
        crud._attach_project_client_fields(peer)
    crud._attach_word_count_matrices(db, projects=others)
    load_finance_details(db, others)
    affected = [(peer, audit.capture(peer)) for peer in others]
    for peer in peers:
        billing_tax.save(db, user, peer, peer, mode)
    db.flush()
    return affected


def finish_settlement_tax(db, user, affected):
    for peer, before in affected:
        confirmations.recheck_after_fee_change(db, peer.id, user.id)
        audit.append(db, user, peer, before)


def sync_statement_month(db, project, scope, value, actor_id, method=None):
    from translation_document_requirements import TranslationProjectDocuments, attach as attach_documents, save as save_documents

    if statement_client_id(project) != scope.client_id or effective_billing_month(project) != scope.billing_month:
        raise HTTPException(409, '项目客户或账单月份已变化，请重新确认同步范围')
    targets = statement_month_projects(db, scope.client_id, scope.billing_month).filter(
        TranslationProject.id != project.id).order_by(TranslationProject.id).with_for_update(of=TranslationProject).populate_existing().all()
    if not targets:
        return 0
    attach_documents(db,targets)
    saved = {row.project_id: row for row in db.query(TranslationProjectDocuments).filter(
        TranslationProjectDocuments.project_id.in_([target.id for target in targets]))}
    changed = 0
    for target in targets:
        required = value if (method or payment_method(target))=='special' else None
        if required is None and method is None:
            continue
        existing = saved.get(target.id)
        if existing and (required is None or existing.statement_required is required) and (
            method is None or (existing.quotation_data or {}).get('_payment_method') == method):
            continue
        save_documents(db, target, statement_required=required, payment_method=method, actor_id=actor_id)
        target.updated_at = business_now().replace(tzinfo=None)
        changed += 1
    return changed


def sync_statement_customer(db, project, scope, value, user, locked_client, payment_method=None, finance_values=None):
    from customer_statements import sync_project_statement_default

    if scope.client_id != locked_client or statement_client_id(project) != scope.client_id:
        raise HTTPException(409, '项目客户已变化，请重新确认客户默认设置')
    sync_project_statement_default(db, scope.client_id, scope.revision, value, user, payment_method, finance_values)


def tree(project, billing_month=None, *, summary_only=False, include_billing_tax_mode=True, include_version=True):
    from customer_finance_sync import reference_tax
    owners, numbers, parents = hierarchy(project)
    db=object_session(project)
    method = payment_method(project)
    settlement_party = getattr(project, 'settlement_party', 'sub_client' if project.sub_client_id else 'client')
    uses_parent_settings = bool(project.sub_client_id and settlement_party == 'client')
    document_defaults = getattr(project, 'customer_document_defaults', {})
    sub_documents = (sub_client_finance.document_settings(
        db.info.get('settlement_workspace_payloads', {}).get(statement_client_id(project)), project.sub_client_id
    ) if db is not None and project.sub_client_id and not uses_parent_settings else {})
    sub_finance = (sub_client_finance.load(db, {project.sub_client_id}).get(project.sub_client_id)
                   if db is not None and project.sub_client_id and not uses_parent_settings else None)
    explicit_modes=order_pricing_modes(db,project)
    total_adjustments=getattr(project,'order_total_adjustments',{})
    meta=rates.metadata(db,[charge.id for owner in owners for charge in owner.customer_charge_items]) if db else {}
    references=getattr(project,'customer_price_defaults',[])
    nodes = {}
    for owner in owners:
        key = str(owner.id); row = primary(owner)
        rate = signature(row)
        nodes[key] = dict(id=key,root_id=str(project.id),order_no=numbers[key],project_name=(project.source_file_name or project.project_name) if owner is project else owner.sub_project_name,
            pricing_mode=row.pricing_mode if row else 'metric',
            direct_pricing=False, fixed_pricing_from=None, _has_fixed_charge=bool(row and row.pricing_mode=='fixed'),
            client_short_name=project.client_short_name or project.client_name or '-',project_status=project.project_status if owner is project else owner.status,
            language_pair=owner.language_pair or project.language_pair, children=[], amount=str(rate[0]) if rate and rate[0] is not None else None,
            currency=rate[1] if rate else 'CNY',metric=rate[2] if rate else 'characters_no_spaces',unit_size=str(rate[3] or 1) if rate else '1',
            adjusted_total=str(row.total_excl_tax) if row and row.total_excl_tax is not None else None,
            adjusted_total_incl_tax=str(row.total_incl_tax) if row and row.total_incl_tax is not None else None,
            billing_month=effective_billing_month(project,owner),recorded_billing_month=row.billing_month if row else None,statement_required=bool(getattr(project,'statement_required',True)),
            quotation_required=bool(getattr(project,'effective_quotation_required',project.quotation_required)),invoice_requirement_override=getattr(project,'effective_invoice_required',None),quotation_draft=getattr(project,'quotation_draft',None),document_notes=dict(getattr(project,'document_notes',{}) or {}),invoice_data=getattr(project,'invoice_data',{}),statement_required_explicit=bool(getattr(project,'statement_required_explicit',False)),
            explanation=row.remarks or '' if row else '',word_count_matrix=owner.word_count_matrix)
        nodes[key]['word_count_matrix_source']=getattr(owner,'word_count_matrix_source','project' if owner is project else 'suborder')
        if not summary_only:nodes[key].update(finance_notes.values(db,project,owner,row))
        nodes[key]['word_count_sub_order_count']=getattr(owner,'word_count_sub_order_count',0)
        nodes[key]['prices']=rates.order_rates(db,owner,owner.language_pair or project.language_pair,meta) if db else []
        effective_client_id=project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)
        nodes[key]['client_id']=str(effective_client_id) if effective_client_id else None
        nodes[key]['sub_client_id']=str(project.sub_client_id) if project.sub_client_id else None
        nodes[key]['settlement_party'] = settlement_party
        nodes[key]['document_sub_client_id'] = nodes[key]['sub_client_id'] if settlement_party == 'sub_client' else None
        nodes[key]['sub_client_invoice_required'] = sub_documents.get('invoice_required')
        nodes[key]['sub_client_statement_required'] = sub_finance.statement_required if sub_finance else None
        nodes[key]['sub_client_short_name']=getattr(project,'sub_client_short_name',None)
        nodes[key]['sub_client_name']=getattr(project,'sub_client_name',None)
        nodes[key]['sub_client_code']=getattr(project,'sub_client_code',None)
        nodes[key]['billing_period']=getattr(project,'billing_period',{})
        nodes[key]['client_manager']=getattr(project,'client_manager',None) or ''
        manager_id=getattr(project,'client_manager_id',None)
        nodes[key]['client_manager_id']=str(manager_id) if manager_id else None
        nodes[key]['payment_method']=method
        if project.sub_client_id and not uses_parent_settings:
            quotation_default = sub_finance.quotation_required if sub_finance else None
            nodes[key]['quotation_required'] = (quotation_default if quotation_default is not None
                                                else bool(project.quotation_required))
            if getattr(project, 'customer_document_sources', {}).get('invoice_required'):
                nodes[key]['invoice_requirement_override'] = None
        if uses_parent_settings:
            nodes[key]['quotation_required'] = bool(document_defaults.get('quotation_required'))
        if nodes[key]['payment_method']=='special' and owner is not project:
            nodes[key]['invoice_requirement_override']=getattr(project,'order_invoice_requirements',{}).get(key,nodes[key]['invoice_requirement_override'])
            nodes[key]['statement_required']=getattr(project,'order_statement_requirements',{}).get(key,nodes[key]['statement_required'])
        nodes[key]['has_monthly_payment_peers']=getattr(project, 'has_monthly_payment_peers', False)
        period_number = getattr(project, 'settlement_period_number', None)
        nodes[key]['settlement_period_number'] = period_number if isinstance(period_number, int) else None
        nodes[key]['statement_status']=getattr(owner,'statement_status',[])
        if owner is project:
            nodes[key]['customer_document_defaults']=getattr(project,'customer_document_defaults',{})
            nodes[key]['customer_document_sources']={**getattr(project,'customer_document_sources',{})}
            if payment_method(project)!='special':
                nodes[key]['customer_document_sources']['invoice_required']=False
            nodes[key]['customer_statements']=getattr(project,'customer_statements',[])
            if db and not summary_only:
                payment = getattr(project, 'payment_confirmation', None)
                nodes[key]['payment_confirmation'] = payment if payment is not None else confirmations.read(db,project.id)
            else:
                nodes[key]['payment_confirmation'] = None
            nodes[key]['statement_required']=bool(getattr(project,'statement_required',True))
            nodes[key]['updated_at']=business_datetime(project.updated_at).isoformat() if project.updated_at else None
    for key, parent in parents.items():
        nodes[parent]['children'].append(nodes[key])

    def calculate(node, inherited=None, fixed_from=None):
        requested = explicit_modes.get(node['id'])
        if node['children'] and requested == 'fixed':
            node.update(pricing_mode='fixed',direct_pricing=True)
        if fixed_from:
            node['fixed_pricing_from'] = fixed_from
            node['pricing_mode'] = 'fixed'
            node['direct_pricing'] = True
            node['prices'] = []
            if not node.pop('_has_fixed_charge'):
                node.update(adjusted_total=None, adjusted_total_incl_tax=None)
        else:
            node.pop('_has_fixed_charge')
        if node['children'] and not node['direct_pricing']:
            from translation_price_rollup import aggregate_node, apply_total_adjustment
            original_children=node['children'];included=[]
            legacy_source=node if node['prices'] and requested!='aggregate' else inherited
            for child in original_children:
                calculate(child,legacy_source)
                if not billing_month or child['matches_month']:included.append(child)
            matches=not billing_month or effective_billing_month(project)==billing_month
            aggregate_node(node,included)
            apply_total_adjustment(node,total_adjustments.get(node['id']),matches or bool(included))
            node['matches_month']=matches or bool(included)
            return
        if node['pricing_mode']=='fixed':
            included=[]
            for child in node['children']:
                calculate(child, fixed_from=fixed_from or node['order_no'])
                if not billing_month or child['matches_month']:included.append(child)
            matches=not billing_month or effective_billing_month(project)==billing_month
            excl={node['currency']:node['adjusted_total']} if node['adjusted_total'] is not None and matches else {}
            incl={node['currency']:node['adjusted_total_incl_tax']} if node['adjusted_total_incl_tax'] is not None and matches else {}
            node.update(children=included,matches_month=matches or bool(included),totals=excl,adjusted_totals=dict(excl),totals_excl_tax=excl,totals_incl_tax=incl,incomplete=not excl and not incl,quantity=None,own_total=None)
            node.update(calculated_totals_excl_tax=excl,calculated_totals_incl_tax=incl)
            from translation_price_rollup import apply_total_adjustment, sum_child_amounts
            for kind in ('excl_tax','incl_tax'):
                field='totals_'+kind
                child_adjustments=sum_child_amounts(included,'adjusted_totals_'+kind)
                child_adjustments={currency:amount for currency,amount in child_adjustments.items() if currency not in node[field]}
                node['adjusted_totals_'+kind]=child_adjustments
                node[field]={**child_adjustments,**node[field]}
            node['adjusted_totals'].update(node['adjusted_totals_excl_tax'])
            apply_total_adjustment(node,total_adjustments.get(node['id']),matches)
            node['incomplete']=not (node['totals_excl_tax'] or node['totals_incl_tax'])
            return
        allow_inheritance=node['id'] not in getattr(project,'cleared_price_orders',())
        if allow_inheritance and not node['direct_pricing'] and not node['prices'] and inherited:
            choices=set(str(node['language_pair'] or '').split('；'))
            node['prices']=[
                {**row,'id':None,'inherited':True,
                 'tax_prices':{**(row.get('tax_prices') or {}),'total_excl_tax':None,'total_incl_tax':None}}
                for row in inherited['prices'] if not node['language_pair'] or row['language_pair'] in choices
            ]
        use_defaults = references and allow_inheritance
        if not node['prices'] and use_defaults:
            node['prices']=[
                {**row,'id':None,'reference_id':row['id'],'reference_revision':row['revision'],
                 'tax_prices':reference_tax(row) or {'unit_price_excl_tax':row['amount']}}
                for row in rate_matching.references_for_new_prices(references,node['language_pair'],node['word_count_matrix'])
            ]
        elif use_defaults:
            for price in node['prices']:
                if price['amount'] is not None or price.get('reference_id'):
                    continue
                reference=rate_matching.automatic_reference(references,price,node['word_count_matrix'])
                if reference:
                    price.update(amount=reference['amount'], reference_id=reference['id'], reference_revision=reference['revision'],
                                 tax_prices={**(reference_tax(reference) or {'unit_price_excl_tax':reference['amount']}),
                                             **{key:value for key,value in price['tax_prices'].items() if key.startswith('total_')}})
        amounts={};missing=False
        tax_amounts={'excl_tax':{},'incl_tax':{}}
        computed_tax={'excl_tax':{},'incl_tax':{}}
        adjusted_currencies={kind:set() for kind in tax_amounts}
        for price in node['prices']:
            if price.get('reference_id'):
                child_refs = getattr(project, 'sub_client_reference_ids', ())
                price['reference_scope'] = 'sub_client' if price['reference_id'] in child_refs else 'client'
            quantity,dimension,actual_metric,quantity_error=quantity_basis.resolve(node['word_count_matrix'],price['metric'])
            price['quantity']=quantity
            price['quantity_dimension']=dimension;price['quantity_metric']=actual_metric;price['quantity_error']=quantity_error
            amount=None if quantity is None or price['amount'] is None else (Decimal(str(quantity))*Decimal(price['amount'])/Decimal(price['unit_size'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
            price['total']=str(amount) if amount is not None else None
            for kind, values in tax_amounts.items():
                tax = price.get('tax_prices') or {}
                total = tax.get('total_'+kind)
                if total is not None:
                    adjusted_currencies[kind].add(price['currency'])
                unit = tax.get('unit_price_'+kind)
                if unit is not None and quantity is not None:computed_tax[kind][price['currency']]=computed_tax[kind].get(price['currency'],Decimal(0))+Decimal(str(quantity))*Decimal(str(unit))/Decimal(price['unit_size'])
                if total is None and unit is not None and quantity is not None:
                    total = Decimal(str(quantity))*Decimal(str(unit))/Decimal(price['unit_size'])
                if total is not None:
                    values[price['currency']] = values.get(price['currency'],Decimal(0))+Decimal(str(total))

            if amount is None:missing=True
            else:amounts[price['currency']]=amounts.get(price['currency'],Decimal(0))+amount
        if not node['direct_pricing'] and node['amount'] is None and inherited and (not inherited['prices'] or node['prices']):
            for key in ('amount','currency','metric','unit_size'):
                node[key] = inherited[key]
            node['inherited'] = True
            node['billing_month'] = node['billing_month'] or inherited.get('billing_month')
        count = node['word_count_matrix'].get('customer', {}).get(node['metric'])
        node['quantity'] = count
        own = None if count is None or node['amount'] is None else (Decimal(str(count))*Decimal(node['amount'])/Decimal(node['unit_size'])).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        node['own_total'] = str(own) if own is not None else None
        totals, adjusted, incomplete = {}, {}, False
        original_children=[] if node['direct_pricing'] else node['children']
        included=[]
        if node['direct_pricing']:
            for child in node['children']:
                calculate(child,inherited)
                if not billing_month or child['matches_month']:included.append(child)
        for child in original_children:
            calculate(child, node if node['amount'] is not None else None)
            if billing_month and not child['matches_month']: continue
            included.append(child)
            incomplete |= child['incomplete']
            for key, value in child['totals'].items(): totals[key] = totals.get(key, Decimal(0))+Decimal(value)
            for key, value in child['adjusted_totals'].items(): adjusted[key] = adjusted.get(key, Decimal(0))+Decimal(value)
        matches=not billing_month or effective_billing_month(project)==billing_month
        if not original_children:
            incomplete = matches and (missing if node['prices'] else own is None)
            if matches and node['prices']:totals.update(amounts)
            elif matches and own is not None: totals[node['currency']] = own
            effective = Decimal(node['adjusted_total']) if node['adjusted_total'] is not None else own
            if matches and node['prices']:adjusted.update(amounts)
            if matches and effective is not None and (node['adjusted_total'] is not None or not node['prices']): adjusted[node['currency']] = effective
        elif node['adjusted_total'] is not None and matches:
            # 父级明确调整金额只覆盖本币种；其他币种仍单列。
            adjusted[node['currency']] = Decimal(node['adjusted_total'])
        for kind in tax_amounts:
            node['calculated_totals_'+kind]={currency:str(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) for currency,value in computed_tax[kind].items()}
            values = {} if original_children else tax_amounts[kind]
            if original_children:
                for child in included:
                    for currency, value in child.get('totals_'+kind,{}).items():
                        values[currency]=values.get(currency,Decimal(0))+Decimal(value)
            override=node.get('adjusted_total' if kind=='excl_tax' else 'adjusted_total_incl_tax')
            if override is not None and matches:
                values[node['currency']]=Decimal(override)
                adjusted_currencies[kind].add(node['currency'])
            node['totals_'+kind]={currency:str(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) for currency,value in values.items()}
            node['adjusted_totals_'+kind]={currency:value for currency,value in node['totals_'+kind].items()
                                          if matches and currency in adjusted_currencies[kind]}
        node.update(children=included,matches_month=matches or bool(included),totals={k:str(v) for k,v in totals.items()},adjusted_totals={k:str(v) for k,v in adjusted.items()},incomplete=incomplete)
        from translation_price_rollup import apply_total_adjustment
        apply_total_adjustment(node,total_adjustments.get(node['id']),matches)
    root=nodes[str(project.id)];calculate(root)
    def count_children(node):
        node['child_order_count'] = sum(1 + count_children(child) for child in node['children'])
        return node['child_order_count']

    count_children(root)
    if root['children']:
        order_directions={str(owner.id):owner.language_pair for owner in owners}
        root['missing_child_orders']=missing_child_order_fields(root,order_directions)
    if include_billing_tax_mode:
        from customer_statements import load_customer_tax_preferences
        client_id = statement_client_id(project)
        default_mode='incl_tax' if db and load_customer_tax_preferences(db,[client_id]).get(client_id) else 'excl_tax'
        stored=billing_tax.modes(db,project.id)
        billing_tax.attach(root,stored,default_mode,unified_tax_mode(db,project,root,stored,default_mode))
        from translation_project_invoices import invoice_required
        for node in nodes.values():
            if uses_parent_settings:
                node['invoice_requirement_override'] = document_defaults.get('invoice_required')
            node['invoice_required'] = invoice_required(node)
    # 对账单需求独立于计费税口径；完整详情及精简列表必须使用同一规则。
    # 没有客户/子客户明确设置时，沿用单据默认值（客户类型、付款状态及项目设置）。
    for node in nodes.values():
        if method != 'special' or project.sub_client_id:
            statement_default = (document_defaults.get('statement_required') if uses_parent_settings
                                 else sub_finance.statement_required if sub_finance else
                                 project.statement_required if getattr(project,'statement_required_explicit',False) else
                                 document_defaults.get('statement_required'))
            if statement_default is not None:
                node['statement_required'] = bool(statement_default)
    if root['payment_method']=='special' and any(node['statement_required'] for node in nodes.values() if not node.get('fixed_pricing_from')):
        root['has_statement_required_orders'] = True
    # 已实际形成对账单的项目/子订单，不再被客户默认值或税口径显示为“不需”。
    for node in nodes.values():
        if node.get('statement_status'):
            node['statement_required']=True
    if root['payment_method']=='special' and any(node['statement_required'] for node in nodes.values() if not node.get('fixed_pricing_from')):
        root['has_statement_required_orders']=True
    return {'item':root,'version':version(project) if include_version and not summary_only else None}


def effective_statement_requirements(db, projects):
    from translation_document_requirements import attach as attach_documents
    from translation_customer_type import attach as attach_customer_types
    from translation_statement_status import attach as attach_statement_status
    attach_customer_types(db, projects)
    attach_documents(db, projects)
    # 与财务列表一致：已有真实对账单的订单不能按历史需求值归入“无需”。
    attach_statement_status(db, projects)
    attach_monthly_payment_peers(db, projects)
    required = {}
    preferences=sub_client_finance.load(db,{project.sub_client_id for project in projects if project.sub_client_id})
    pending=[]
    for project in projects:
        if getattr(project,'statement_status',None):
            required[project.id]=True
            continue
        if payment_method(project)!='special':
            defaults=getattr(project,'customer_document_defaults',{})
            preference=preferences.get(project.sub_client_id)
            uses_parent=project.sub_client_id and getattr(project,'settlement_party',None)=='client'
            value=(defaults.get('statement_required') if uses_parent else
                   preference.statement_required if preference else
                   project.statement_required if getattr(project,'statement_required_explicit',False) else
                   defaults.get('statement_required'))
            if value is not None:
                required[project.id]=bool(value)
                continue
        pending.append(project)
    if not pending:
        return required
    preload_monthly_tax_projects(db, pending)
    load_finance_details(db, pending, tax_only=True)
    crud._attach_word_count_matrices(db, projects=pending)
    from project_client_manager import attach as attach_managers
    attach_managers(db,'translation',pending)
    for project in pending:
        crud._attach_project_client_fields(project)
        root = tree(project, summary_only=True)['item']
        required[project.id] = root['statement_required'] or root.get('has_statement_required_orders', False)
    return required


def load_finance_details(db, projects, *, tax_only=False):
    from customer_statements import load_customer_tax_preferences

    project_ids = [project.id for project in projects]
    sub_client_finance.load(db, {project.sub_client_id for project in projects if project.sub_client_id})
    load_customer_tax_preferences(db, [project.client_id for project in projects])
    billing_tax.load_modes(db, project_ids)
    attach_customer_price_defaults(db, projects)
    if not tax_only:
        finance_notes.load_rows(db, project_ids)


def attach_customer_price_defaults(db, projects):
    owners = {project.id: project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)
              for project in projects}
    references = {}
    child_references = {}
    if any(owners.values()) and rates.ready(db):
        model = rates.CustomerTranslationRate
        query = db.query(model).filter(model.client_id.in_({key for key in owners.values() if key}),model.active.is_(True))
        for row in query.filter(~model.rate_key.startswith('sub:')).all():
            references.setdefault(row.client_id, []).append(rates.serialize(row))
        child_ids = {p.sub_client_id for p in projects if p.sub_client_id}
        if child_ids and rates.sub_rates_ready(db):
            scope = rates.SubClientTranslationRate
            for row, sub_id in query.join(scope, scope.rate_id == model.id).add_columns(scope.sub_client_id).filter(scope.sub_client_id.in_(child_ids)):
                child_references.setdefault((row.client_id, sub_id), []).append(rates.serialize(row))
    for project in projects:
        client_id = owners[project.id]
        child_rates = child_references.get((client_id, project.sub_client_id), [])
        project.sub_client_reference_ids = {row['id'] for row in child_rates}
        project.customer_price_defaults = rates.project_rate_defaults(references.get(client_id, []), child_rates)


def missing_child_order_fields(root, order_directions):
    missing = {'language_pair': [], 'word_count': [], 'unit_price': []}

    def visit(node):
        if node['children']:
            for child in node['children']:
                visit(child)
            return

        directions = {value.strip() for value in (order_directions.get(node['id']) or '').split('；') if value.strip()}
        order_no = node['order_no']
        if not directions:
            missing['language_pair'].append(order_no)
        if matches_missing_fields(node, word_count=True):
            missing['word_count'].append(order_no)
        if node['pricing_mode'] != 'fixed':
            priced_directions = set()
            has_empty_rate = False
            for price in node['prices']:
                tax = price.get('tax_prices') or {}
                if any(value is not None for value in (price.get('amount'), tax.get('unit_price_excl_tax'), tax.get('unit_price_incl_tax'))):
                    priced_directions.add(price.get('language_pair'))
                else:
                    has_empty_rate = True
            if not priced_directions or has_empty_rate or directions - priced_directions:
                missing['unit_price'].append(order_no)

    for child in root['children']:
        visit(child)
    return missing


def read(db, project_id):
    # Reload the order tree and all charge collections in batches. Expiring each
    # collection after the eager load causes a separate query per sub-order.
    project=crud.get_translation_project(db,project_id,refresh=True)
    if not project: raise HTTPException(404,'笔译项目不存在')
    attach_monthly_payment_peers(db,[project])
    attach_customer_price_defaults(db,[project])
    result=tree(project)
    from customer_statements import CustomerStatementPreference
    client_id=project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)
    if client_id:
        preference=db.get(CustomerStatementPreference,client_id)
        result['item']['customer_preference_revision']=preference.revision if preference else 0
    result['document_consistency_review'] = getattr(project, 'document_consistency_review', None)
    from translation_payment_service import read as read_payments
    result['payment']=read_payments(db,project)
    result['reference_prices']=rates.library(db,client_id) if client_id else {'ready':rates.ready(db),'items':[],'version':''}
    if client_id and project.sub_client_id:
        result['sub_client_reference_prices'] = rates.library(db, client_id, project.sub_client_id)
    return result


def document_consistency_rows(root):
    """Compare effective requirements for the mother order and all descendants."""
    values = []

    def visit(order, inherited_invoice=None, inherited_tax=None):
        invoice = inherited_invoice if order.get('fixed_pricing_from') else order.get('invoice_required')
        tax = inherited_tax if order.get('fixed_pricing_from') else order.get('effective_billing_tax_mode')
        values.append(dict(id=order['id'], order_no=order['order_no'], quotation=bool(order['quotation_required']),
                           statement=bool(order['statement_required']), invoice=invoice, tax=tax,
                           fixed_pricing_from=order.get('fixed_pricing_from'),
                           totals_excl_tax=order.get('totals_excl_tax', {}), totals_incl_tax=order.get('totals_incl_tax', {})))
        for child in order['children']:
            visit(child, invoice, tax)

    visit(root)
    return values


def save_document_consistency_review(db, user, project_id, submitted):
    from translation_document_requirements import save_consistency_review
    project = crud.get_translation_project(db, project_id, refresh=True)
    attach_monthly_payment_peers(db, [project])
    method = payment_method(project)
    rows = document_consistency_rows(tree(project, include_version=False)['item']) if method in (*GROUPED_SETTLEMENT_MODES,'statement') else []
    previous = project.document_consistency_review
    snapshot = [(row['id'], row['quotation'], row['statement'], row['invoice'], row['tax']) for row in rows]
    if any(row[1:] != snapshot[0][1:] for row in snapshot[1:]):
        reason = submitted.reason.strip()
        if submitted.snapshot != snapshot or not reason:
            raise HTTPException(409, dict(code='document_consistency_review', rows=rows,
                message='请核对各订单的单据需求和计费口径，统一设置或填写保留差异的理由'))
        review = {'method': method, 'snapshot': [list(value) for value in snapshot], 'reason': reason}
    else:
        review = None
    if previous != review:
        save_consistency_review(db, project, review, user.id)
        base = {'order_no': project.order_no, 'project_name': project.project_name}
        key = str(project_id)
        audit.append_snapshots(db, user, project_id,
            {key: {**base, 'document_consistency_review': previous}},
            {key: {**base, 'document_consistency_review': review}})


def payment_match_order(node):
    return {**{field:node[field] for field in (
        'id','order_no','project_name','totals_excl_tax','totals_incl_tax','billing_totals','incomplete','prices'
    )}, 'fixed_pricing_from':node.get('fixed_pricing_from'),
        'children':[payment_match_order(child) for child in node['children']]}


def settlement_order_details(order, node, inherited=None):
    fixed = node['fixed_pricing_from']
    aggregate = bool(node.get('price_aggregate'))
    order['price_aggregate'] = aggregate
    order['pricing_mode'] = node['pricing_mode']
    order['billing_tax_pending'] = bool(node.get('billing_tax_pending'))
    order['document_requirements'] = dict(
        quotation=node['quotation_required'], statement=node['statement_required'],
        invoice=inherited['invoice'] if fixed and inherited else node['invoice_required'],
        tax=inherited['tax'] if fixed and inherited else node['effective_billing_tax_mode'],
    )
    order['billing_tax_choices'] = (
        [] if aggregate or fixed else billing_tax.available(node)
    )
    for child, child_node in zip(order['children'], node['children']):
        settlement_order_details(child, child_node, order['document_requirements'])


def payment_summary(db, project, method=None, *, include_orders=False):
    """汇总母订单金额，已生成对账单以实际入账的账单为准。"""
    attach_monthly_payment_peers(db, [project])
    if method is None:
        method = payment_method(project)
        if method=='monthly' and tree(project,summary_only=True)['item']['statement_required']:
            method='statement'
    client_id, month = statement_client_id(project), effective_billing_month(project)
    result = dict(method=method, month=month, totals_excl_tax={}, totals_incl_tax={}, billing_totals={},
                  internal_notes=[], customer_notes=[], pending=False, board_name=None)
    if method in GROUPED_SETTLEMENT_MODES:
        result['order_count'] = 0
        if include_orders:
            result['orders'] = []
    if method in ('individual','special') or not client_id or not month or method=='sub_client' and not project.sub_client_id:
        return result

    def add_totals(field, amounts):
        totals = result[field]
        for currency, amount in amounts.items():
            totals[currency] = Decimal(totals.get(currency, 0)) + Decimal(amount)

    def add_notes(node, customer=True):
        for field, note in [('internal_notes', node.get('explanation')), ('customer_notes', node.get('customer_explanation') if customer else None)]:
            if note:
                result[field].append(f"{node['order_no']}  {note}")

    if method == 'statement':
        from customer_statement_workspace import StatementWorkspace, display_rows
        from translation_statement_status import attach as attach_statement_status
        attach_statement_status(db, [project])
        boards = getattr(project, 'statement_status', [])
        if len(boards) > 1:
            result.update(pending=True, message='项目关联多张对账单，请先核对实际付款对应的对账单。')
            return result
        if boards:
            link = boards[0]
            workspace = db.get(StatementWorkspace, UUID(link['client_id']))
            if workspace:
                board = next((entry for entry in workspace.payload['boards'] if entry['id'] == link['board_id']), None)
                if board and (payment_method(project)!='sub_client' or board.get('sub_client_id')==str(project.sub_client_id)):
                    _, lines = display_rows(workspace.payload, board)
                    result.update(board_name=board['name'], statement_projects=[])
                    roots = {}
                    for line in lines:
                        roots.setdefault(line['root_id'], set()).add(line['billing_month'])
                        if not line.get('counted_in_total', True):
                            continue
                        if line['subtotal'] is not None:
                            label = line.get('unit_label')
                            incl = label == '含税' if label in ('含税', '不含税') else board['tax_included']
                            add_totals('totals_incl_tax' if incl else 'totals_excl_tax', {line['currency']: line['subtotal']})
                            add_totals('billing_totals', {line['currency']: line['subtotal']})
                        else:
                            result['pending'] = True
                        if line.get('remarks'):
                            result['customer_notes'].append(f"{line['order_no']}  {line['remarks']}")
                    for order in db.query(TranslationProject).filter(TranslationProject.id.in_([UUID(key) for key in roots])).order_by(TranslationProject.order_no):
                        charge = primary(order)
                        add_notes({'order_no': order.order_no, **finance_notes.values(db, order, order, charge)}, customer=False)
                        result['statement_projects'].append(dict(id=str(order.id), order_no=order.order_no,
                            project_name=order.project_name, billing_month='、'.join(sorted(roots[str(order.id)]))))
                    return result

    fields = {'finance_client_ids': {'value': [str(client_id)]}, 'finance_billing_month': {'value': month}}
    projects = crud.get_translation_projects(db, limit=None, field_filters=fields)
    attach_monthly_payment_peers(db, projects)
    period = project.settlement_period_number
    requested_group = settlement_group_key(project)
    projects = [peer for peer in projects if peer.id == project.id or (
        peer.settlement_period_number == period and
        (settlement_group_key(peer) == requested_group if requested_group[3]=='sub_client' else payment_method(peer)=='monthly')
    )]
    load_charge_metadata(db, projects)
    load_finance_details(db, projects)
    for peer in projects:
        node = tree(peer, include_version=False)['item']
        if method=='statement' and peer.id != project.id and not node['statement_required']:
            continue
        for field in ('totals_excl_tax', 'totals_incl_tax', 'billing_totals'):
            add_totals(field, node[field])
        result['pending'] |= node['incomplete'] or not node['billing_totals']
        add_notes(node)
        if method in GROUPED_SETTLEMENT_MODES:
            result['order_count'] += 1
            if include_orders:
                order = payment_match_order(node)
                settlement_order_details(order, node)
                result['orders'].append(order)
    if method in GROUPED_SETTLEMENT_MODES and include_orders:
        from translation_payment_filters import attach_payment_status, settlement_payment_states
        attach_payment_status(db, {'items':result['orders']}, check_amount=False,
                              settlement_states=settlement_payment_states(db,projects))
    if method == 'statement':
        result['message'] = '对账单尚未生成，当前按本月需对账单的项目预估。'
    return result


def load_charge_metadata(db,projects):
    ids=[charge.id for project in projects for owner in [project,*project.sub_orders] for charge in owner.customer_charge_items]
    for offset in range(0,len(ids),4000):
        batch=ids[offset:offset+4000]
        rates.metadata(db,batch)
        quantity_basis.metadata(db,batch)


def client_subtotals(db, filters):
    query=db.query(TranslationProject).options(joinedload(TranslationProject.client),joinedload(TranslationProject.sub_client),selectinload(TranslationProject.customer_charge_items),
        selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.customer_charge_items)).outerjoin(Client,TranslationProject.client_id==Client.id).outerjoin(SubClient,TranslationProject.sub_client_id==SubClient.id).filter(TranslationProject.annotation_migrated_at.is_(None))
    projects=crud._apply_translation_project_filters(query,**filters).all()
    from translation_document_requirements import load_order_pricing_modes
    load_order_pricing_modes(db, projects)
    sub_client_finance.load(db, {project.sub_client_id for project in projects if project.sub_client_id})
    crud._attach_word_count_matrices(db,projects=projects)
    load_charge_metadata(db,projects)
    attach_customer_price_defaults(db,projects)
    groups={}
    for project in projects:
        project.client_short_name=(project.client.client_short_name or project.client.client_name) if project.client else '-'
        project.client_name=project.client.client_name if project.client else '-'
        key=str(project.client_id) if project.client_id else 'unassigned'
        group=groups.setdefault(key,{'client_id':key,'client_name':project.client_short_name,'project_count':0,'totals':{},'adjusted_totals':{},'totals_excl_tax':{},'totals_incl_tax':{},'incomplete':False})
        month=(filters.get('field_filters') or {}).get('finance_billing_month',{}).get('value')
        node=tree(project,month,summary_only=True,include_billing_tax_mode=False)['item'];group['project_count']+=1;group['incomplete']|=node['incomplete']
        for field in ('totals','adjusted_totals','totals_excl_tax','totals_incl_tax'):
            for currency,amount in node[field].items():group[field][currency]=group[field].get(currency,Decimal(0))+Decimal(amount)
    for group in groups.values():
        for field in ('totals','adjusted_totals','totals_excl_tax','totals_incl_tax'):group[field]={key:str(value) for key,value in group[field].items()}
    return sorted(groups.values(),key=lambda row:row['client_name'])


def record_order_rates(db,user,project,owner,order_no,previous,current,*,initial=False):
    from customer_finance_sync import signature as finance_signature, number, tax_signature
    client_id=statement_client_id(project)
    if not client_id:
        return

    def snapshot(items):
        return [{**{field:item[field] for field in ('language_pair','currency','metric')},
                 'amount':number(item['amount']), 'unit_size':number(item['unit_size']),
                 'tax_prices':dict(zip(('unit_price_excl_tax','unit_price_incl_tax'),tax_signature(item)))}
                for item in items if item['amount'] is not None]

    before=[] if initial else snapshot(previous)
    after=snapshot(current)
    if finance_signature('translation',before)==finance_signature('translation',after):
        return
    library=rates.library(db,client_id)['items']
    matches_customer=bool(after) and all(
        (reference:=rate_matching.automatic_reference(library,item,owner.word_count_matrix)) is not None
        and number(reference['amount'])==item['amount'] and tax_signature(reference)==tax_signature(item)
        for item in after
    )
    rates.record_order_finance(db,user,client_id,owner.id,order_no,'order_rates',before,after,
                              matches_customer=matches_customer,initial=initial)


def save_prices(db,user,project,owners,parents,key,payload):
    if not rates.ready(db):raise HTTPException(503,'客户语种单价存储尚未初始化')
    values=[rates.normalize(db,item) for item in payload.prices]
    keys=[rates.rate_key(item) for item in values]
    if len(set(keys))!=len(keys):raise HTTPException(422,'同语种、货币、计价口径的单价不能重复')
    if payload.adjusted_total is not None and len({item['currency'] for item in values})>1:raise HTTPException(422,'存在多个币种时请分别在下级订单调整金额')
    target=owners[key]
    own_ids={row.id for row in target.customer_charge_items if row.pricing_mode=='metric'}
    submitted_ids=[item.id for item in payload.prices if item.id]
    if len(set(submitted_ids))!=len(submitted_ids):raise HTTPException(422,'同一收费项不能重复提交，请删除重复单价')
    if any(item.id and item.id not in own_ids for item in payload.prices):raise HTTPException(422,'单价不属于当前订单，请重新打开后编辑')
    client_id = statement_client_id(project)
    active_rate = rates.CustomerTranslationRate.active.is_(True)
    parent_refs = rates.scoped_rates(db, client_id).filter(active_rate).all() if client_id else []
    child_refs = rates.scoped_rates(db, client_id, project.sub_client_id).filter(active_rate).all() if client_id and project.sub_client_id else []
    references = {row.id: row for row in [*parent_refs, *child_refs]}
    if references and any(data['amount'] is None for data in values):
        quotes = rates.project_rate_defaults(list(map(rates.serialize, parent_refs)), list(map(rates.serialize, child_refs)))
        for data in values:
            if data['amount'] is not None or data.get('reference_id'):
                continue
            reference=rate_matching.automatic_reference(quotes,data,target.word_count_matrix)
            if reference:
                tax=reference.get('tax_prices') or {'unit_price_excl_tax':reference['amount']}
                data.update(amount=Decimal(reference['amount']),
                            tax_prices={key:Decimal(value) if value is not None else None for key,value in tax.items()},
                            reference_id=UUID(reference['id']),reference_revision=reference['revision'])
    for data in values:
        ref_id=data.get('reference_id')
        if ref_id:
            old_meta=db.get(rates.TranslationChargeDirection,data['id']) if data.get('id') in own_ids else None
            old_price=next((row for row in rates.order_rates(db,target,target.language_pair or project.language_pair) if row.get('id')==str(data.get('id'))),None)
            if old_meta and old_meta.reference_id==ref_id and old_meta.reference_revision==data.get('reference_revision') and old_price and rates.rate_key(old_price)==rates.rate_key(data):continue
            ref=references.get(ref_id)
            if not ref or ref.revision!=data.get('reference_revision') or not rate_matching.matches(rates.serialize(ref),data,right_matrix=target.word_count_matrix,left_reference=True):raise HTTPException(409,'所采用的客户参考价已变化或不匹配，请重新选择')
    if payload.update_library:
        if not user_has_permission(db,user.id,'clients:write'):raise HTTPException(403,'同步客户参考价需要客户管理编辑权限')
        if not payload.sync_confirmed:raise HTTPException(422,'请点击并确认同步客户参考价')
        if not client_id:raise HTTPException(422,'请先为项目选择客户')
        from translation_rate_matching import matches,unit
        library_items=[]
        for data in values:
            metric=unit(data['metric'],target.word_count_matrix)
            if not metric:raise HTTPException(422,'同步客户报价前，请先明确项目计量单位')
            candidates=[ref for ref in (child_refs if project.sub_client_id else parent_refs) if matches(rates.serialize(ref),data,right_matrix=target.word_count_matrix,left_reference=True)]
            if len(candidates)>1:raise HTTPException(422,'客户报价存在多条完整匹配项，请先编辑客户报价消除重复')
            library_items.append(rates.RateInput(**{**data,'id':None,'reference_id':None,'reference_revision':None,'metric':candidates[0].metric if candidates else 'customer_auto:'+metric}))
        order_no = project.order_no if target is project else target.sub_order_no
        rates.write_library(db,user,client_id,library_items,payload.library_version,origin='project',merge=True,
                            sub_client_id=project.sub_client_id,project_id=project.id,order_id=target.id,order_no=order_no)
        by_key={rates.rate_key(rates.serialize(row)):row for row in rates.scoped_rates(db,client_id,project.sub_client_id).filter(active_rate)}
        for data,library_item in zip(values,library_items):data.update(reference_id=by_key[rates.rate_key(library_item.model_dump())].id,reference_revision=by_key[rates.rate_key(library_item.model_dump())].revision)
    old={uid:rates.order_rates(db,owner,owner.language_pair or project.language_pair) for uid,owner in owners.items()}
    def comparable(items):
        from customer_finance_sync import tax_signature
        return {rates.rate_key(item):((str(Decimal(str(item['amount'])).normalize()) if item['amount'] is not None else None), tax_signature(item)) for item in items}
    moment=business_now().replace(tzinfo=None)
    def write(owner,items,explicit):
        for fixed in list(owner.customer_charge_items):
            if fixed.pricing_mode=='fixed':owner.customer_charge_items.remove(fixed);db.delete(fixed)
        existing=[row for row in owner.customer_charge_items if row.pricing_mode=='metric'];by_id={row.id:row for row in existing}
        by_key={rates.rate_key(item):by_id[UUID(item['id'])] for item in rates.order_rates(db,owner,owner.language_pair or project.language_pair)}
        kept=set()
        for index,data in enumerate(items):
            row=by_id.get(data.get('id')) if explicit else None
            row=row or by_key.get(rates.rate_key(data))
            if row is None:
                row=TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=project.id if owner is project else None,sub_order_id=None if owner is project else owner.id,created_at=moment)
                owner.customer_charge_items.append(row)
            kept.add(row.id)
            row.item_name='翻译费';row.pricing_mode='metric';row.sequence_no=index+1
            tax=data.get('tax_prices')
            row.unit_price_excl_tax=tax.get('unit_price_excl_tax') if tax is not None else data['amount']
            if tax is not None:row.unit_price_incl_tax=tax.get('unit_price_incl_tax')
            row.unit_price=row.unit_price_excl_tax
            if row.unit_price_excl_tax is None and row.unit_price_incl_tax is None:
                row.unit_price=data['amount']
            row.currency=data['currency'];row.metric_type=quantity_basis.storage_metric(quantity_basis.resolve(owner.word_count_matrix,data['metric'])[2]);row.unit_size=data['unit_size']
            row.billing_month=payload.billing_month
            if explicit:row.total_excl_tax=row.amount_override=payload.adjusted_total if index==0 else None
            if explicit:row.total_incl_tax=payload.adjusted_total_incl_tax if index==0 else None
            if explicit:row.remarks=payload.explanation
            row.updated_at=moment
            db.flush()
            quantity_basis.store(db,row,data['metric'],owner.word_count_matrix)
            meta=db.get(rates.TranslationChargeDirection,row.id)
            if meta is None:meta=rates.TranslationChargeDirection(charge_id=row.id);db.add(meta)
            meta.language_pair=data['language_pair'];meta.reference_id=data.get('reference_id');meta.reference_revision=data.get('reference_revision')
        for row in existing:
            if row.id not in kept:
                if quantity_basis.ready(db):
                    basis=db.get(quantity_basis.TranslationChargeQuantityBasis,row.id)
                    if basis:db.delete(basis)
                meta=db.get(rates.TranslationChargeDirection,row.id)
                if meta:db.delete(meta)
                owner.customer_charge_items.remove(row);db.delete(row)
        owner.updated_at=moment
    write(target,values,True);changed={key:values}
    direct_modes={key for key,mode in order_pricing_modes(db,project).items() if mode=='fixed'}
    for uid,owner in owners.items():
        parent=parents.get(uid)
        if parent not in changed or parent in direct_modes or uid in direct_modes:continue
        before=comparable(old[uid]);parent_before=comparable(old[parent])
        if before and not all(k in parent_before and parent_before[k]==value for k,value in before.items()):continue
        choices=set(str(owner.language_pair or project.language_pair or '').split('；'))
        inherited=[item for item in changed[parent] if not choices or choices=={''} or item['language_pair'] in choices]
        if inherited:write(owner,inherited,False);changed[uid]=inherited
    project.updated_at=moment
    rates.invalidate_metadata(db)
    quantity_basis.invalidate(db)
    if not payload.update_library:
        record_order_rates(db,user,project,target,hierarchy(project)[1][key],old[key],values,
                           initial=payload.record_initial_finance)
        # 单价保存与客户参考价属于同一事务；空价格和订单总额不进入参考价。
        if client_id:
            from customer_finance_sync import number, tax_signature
            scoped = rates.library(db,client_id,project.sub_client_id)
            updates=[]
            for data in values:
                if data['amount'] is None:
                    continue
                ref=rate_matching.automatic_reference(scoped['items'],data,target.word_count_matrix)
                if ref and number(ref['amount'])==number(data['amount']) and tax_signature(ref)==tax_signature(data):
                    continue
                metric=ref['metric'] if ref else data['metric']
                updates.append(rates.RateInput(**{**data,'id':None,'reference_id':None,'reference_revision':None,'metric':metric}))
            if updates:
                rates.write_library(db,user,client_id,updates,scoped['version'],origin='automatic_project',merge=True,
                                    sub_client_id=project.sub_client_id,project_id=project.id,order_id=target.id,
                                    order_no=hierarchy(project)[1][key])



def save_payment_changes(db,project,payload,actor_id):
    if payload.payment_draft is not None:
        if not payload.payment_version:raise HTTPException(422,'请先加载付款明细，再保存修改')
        from translation_payment_service import save as save_payments
        save_payments(db,project,payload.payment_draft,payload.payment_version,actor_id,payload.payment_confirmation)
    elif payload.payment_confirmation is not None:
        confirmations.save(db,project.id,payload.payment_confirmation,actor_id)
    else:
        confirmations.recheck_after_fee_change(db,project.id,actor_id)


def inherits_fixed_pricing(project, parents, order_key):
    modes = order_pricing_modes(object_session(project), project)
    parent = parents.get(order_key)
    while parent:
        if modes.get(parent) == 'fixed':
            return True
        parent = parents.get(parent)
    return False


def write_total_adjustment(db, user, project, order_key, adjustment, currency=None, pricing_mode=None):
    from translation_special_settlement import order_nodes
    node=next(node for node in order_nodes(tree(project,include_version=False)['item']) if node['id']==order_key)
    if (adjustment.model_fields_set & {'excl_tax','incl_tax'} and
        not (node['pricing_mode'] in ('aggregate','fixed') or pricing_mode in ('aggregate','fixed'))):
        raise HTTPException(422,'工作量计价请使用订单调整后金额字段')
    currency=currency or (node.get('total_adjustment') or {}).get('currency',node['currency'])
    save_order_total_adjustment(db,project,order_key,adjustment.model_dump(exclude_unset=True),currency,user.id)
    db.flush()


def _write_finance(db, user, project_id, payload, *, allow_incomplete=False):
    previous=crud.get_translation_project(db,project_id) if payload.payment_method=='special' else None
    if previous is not None:
        from translation_document_requirements import attach
        attach(db,[previous])
    entering_special=previous is not None and payment_method(previous)!='special'
    _apply_finance(db,user,project_id,payload,allow_incomplete=allow_incomplete)
    if not entering_special:
        return
    db.flush()
    rates.invalidate_metadata(db)
    project=crud.get_translation_project(db,project_id,refresh=True)
    node=tree(project,include_billing_tax_mode=False,include_version=False)['item']

    def validate_price(item):
        if item.get('price_aggregate'):
            for child in item['children']:
                validate_price(child)
            return
        if item['pricing_mode']!='fixed' and (not item['prices'] or any(
            price['amount'] is None and not any((price.get('tax_prices') or {}).get('unit_price_'+mode) is not None
                                                for mode in ('excl_tax','incl_tax'))
            for price in item['prices']
        )):
            raise HTTPException(422,f"{item['order_no']} 请先填写单价，再改为特殊结算")
        if not item['totals_excl_tax'] and not item['totals_incl_tax']:
            raise HTTPException(422,f"{item['order_no']} 请先填写或算出至少一个不含税或含税总价，再改为特殊结算")

    validate_price(node)


def _apply_finance(db, user, project_id, payload, *, allow_incomplete=False):
    audit.require_ready(db)
    db.info.pop('translation_monthly_tax_projects',None)
    db.info.pop('translation_monthly_tax_modes',None)
    if payload.metric not in METRICS: raise HTTPException(422,'请选择有效的计价单位')
    payment_fields={'version','order_id','documents_only','payment_confirmation','payment_draft','payment_version'}
    payment_only=payload.documents_only and payload.model_fields_set <= payment_fields and (
        payload.payment_confirmation is not None or payload.payment_draft is not None
    )
    client_id=None if payment_only else project_statement_client_id(db,project_id)
    if client_id:db.query(Client).filter_by(id=client_id).with_for_update().populate_existing().first()
    project=db.query(TranslationProject).filter_by(id=project_id).filter(TranslationProject.annotation_migrated_at.is_(None)).with_for_update().populate_existing().first()
    if not project: raise HTTPException(404,'笔译项目不存在')
    db.query(TranslationSubOrder).filter_by(parent_project_id=project_id).order_by(TranslationSubOrder.id).with_for_update().populate_existing().all()
    project=crud.get_translation_project(db,project_id)
    if payload.payment_method == 'sub_client' and not project.sub_client_id:
        raise HTTPException(422,'请先在项目登记子客户')
    if version(project)!=payload.version: raise HTTPException(409,'订单价格、字数或下级订单已变化，请重新打开后编辑')
    if not payload.documents_only or payload.order_pricing_mode is not None:
        from translation_entry_deadlines import project_status
        project_status(db, project_id)
    owners,numbers,parents=hierarchy(project);by_id={str(row.id):row for row in owners};key=str(payload.order_id)
    if key not in by_id: raise HTTPException(422,'订单不属于该笔译项目')
    mode=payload.order_pricing_mode or order_pricing_modes(db,project).get(key)
    if key in parents.values() and (payload.adjusted_total is not None or payload.adjusted_total_incl_tax is not None):
        if mode!='fixed':
            raise HTTPException(422,'请使用订单总价调整字段保存汇总金额')
    if inherits_fixed_pricing(project, parents, key) and (
        not payload.documents_only or payload.order_pricing_mode is not None or 'billing_tax_mode' in payload.model_fields_set
    ):
        raise HTTPException(422,'该订单继承上级固定收费，请在上级订单调整计价方式及金额')
    if payment_only:
        save_payment_changes(db,project,payload,user.id)
        return
    month=effective_billing_month(project)
    if month:payload=payload.model_copy(update={'billing_month':month})
    attach_monthly_payment_peers(db,[project])
    if payload.documents_only and payload.document_consistency_review is not None and payload.model_fields_set <= {
        'version', 'order_id', 'documents_only', 'document_consistency_review'
    }:
        return
    before=audit.capture(project)
    if payload.clear_finance and key in getattr(project,'order_total_adjustments',{}):
        save_order_total_adjustment(db,project,key,dict.fromkeys(OrderTotalAdjustment.model_fields),payload.currency,user.id)
    elif payload.total_adjustment is not None and payload.total_adjustment.model_fields_set:
        currency=payload.currency if not payload.documents_only and payload.pricing_mode=='fixed' else None
        write_total_adjustment(db,user,project,key,payload.total_adjustment,currency,mode or payload.pricing_mode)
    elif not payload.documents_only and payload.pricing_mode=='fixed':
        stored=getattr(project,'order_total_adjustments',{}).get(key)
        if stored and stored['currency']!=payload.currency:
            save_order_total_adjustment(db,project,key,{},payload.currency,user.id)
    if payload.order_pricing_mode is not None:
        if key not in parents.values():
            raise HTTPException(422,'仅有下级的订单可切换汇总计价方式')
        if payload.order_pricing_mode == 'metric':
            raise HTTPException(422,'有子订单的订单只能选择子订单汇总或固定收费')
        if payload.order_pricing_mode != 'aggregate' and payload.order_pricing_mode != payload.pricing_mode:
            raise HTTPException(422,'订单计价方式与收费明细不一致')
        owner = by_id[key]
        if payload.order_pricing_mode == 'aggregate' and order_pricing_modes(db, project).get(key) == 'fixed':
            for charge in owner.customer_charge_items:
                if charge.pricing_mode == 'fixed':
                    charge.total_excl_tax = charge.total_incl_tax = charge.amount_override = None
                    charge.updated_at = business_now().replace(tzinfo=None)
        save_order_pricing_mode(db,project,owner.id,payload.order_pricing_mode,user.id)
        if payload.order_pricing_mode == 'aggregate':
            payload=payload.model_copy(update={'documents_only':True})
    from translation_document_requirements import save as save_documents
    from customer_statements import record_order_documents
    target_method = payload.payment_method or payment_method(project)
    use_sub_client = bool(project.sub_client_id and project.settlement_party == 'sub_client')
    child_document = key != str(project.id) and target_method=='special'
    policies = {field:getattr(payload,field) for field in ('statement_required','quotation_required','invoice_required')
                if getattr(payload,field) is not None}
    if policies:
        if use_sub_client:
            sub_client_finance.write_preferences(db,project.sub_client_id,policies.copy(),user,revision=None)
            payload = payload.model_copy(update=dict.fromkeys(policies))
    record_order_documents(db,user,project,client_id,statement_default=None if child_document else payload.statement_required,
                           quotation_required=payload.quotation_required,invoice_required=None if child_document else payload.invoice_required,
                           payment_method=payload.payment_method, initial=payload.record_initial_finance)
    save_documents(db,project,statement_required=payload.statement_required,quotation_required=payload.quotation_required,
                   invoice_required=payload.invoice_required,quotation_draft=payload.quotation_draft,
                   document_notes=payload.document_notes,payment_method=payload.payment_method,
                   document_order_id=payload.order_id if child_document else None,actor_id=user.id)
    affected_tax_peers = []
    if 'billing_tax_mode' in payload.model_fields_set:
        affected_tax_peers = save_settlement_tax(db, user, project, by_id[key], payload.billing_tax_mode)

    def finish_payment():
        save_payment_changes(db,project,payload,user.id)
        finish_settlement_tax(db,user,affected_tax_peers)
    if payload.statement_required is not None and not child_document:
        project.statement_required=payload.statement_required
        project.statement_required_explicit=True
    if payload.statement_sync is not None:
        if payload.statement_required is None and payload.payment_method is None:
            raise HTTPException(422, '请先选择结算模式或是否需对账单')
        if payload.statement_sync.client_id != client_id:
            raise HTTPException(409, '项目客户已变化，请重新确认同步范围')
        sync_statement_month(db, project, payload.statement_sync, payload.statement_required, user.id, payload.payment_method)
    if payload.statement_customer_sync is not None:
        finance_values = {}
        fields = payload.statement_customer_sync.document_fields
        if fields is None:
            fields = ('quotation_required','invoice_required') if payload.statement_customer_sync.sync_document_requirements else ()
        finance_values = {field:getattr(payload,field) for field in fields if getattr(payload,field) is not None}
        if payload.statement_required is None and payload.payment_method is None and not finance_values:
            raise HTTPException(422, '请选择要同步的财务设置')
        sync_statement_customer(db, project, payload.statement_customer_sync, payload.statement_required, user,
                                client_id, None if payload.payment_method=='special' else payload.payment_method, finance_values)
    if policies and not use_sub_client:
        from customer_statements import auto_sync_document_defaults
        auto_sync_document_defaults(db,user,client_id,
            statement_default=('required' if policies['statement_required'] else 'not_required') if 'statement_required' in policies else None,
            quotation_required=policies.get('quotation_required'),invoice_required=policies.get('invoice_required'))
    if payload.quotation_draft is not None:project.quotation_draft=payload.quotation_draft.model_dump(mode='json')
    if payload.documents_only:
        finance_notes.apply(db,user,project,by_id[key],internal=payload.explanation if 'explanation' in payload.model_fields_set else None,customer=payload.customer_explanation)
        finish_payment()
        project.updated_at=business_now().replace(tzinfo=None)
        audit.append(db,user,project,before)
        return
    finance_notes.apply(db,user,project,by_id[key],internal=payload.explanation if 'explanation' in payload.model_fields_set else None,customer=payload.customer_explanation)
    if payload.clear_finance:
        if payload.update_library or payload.prices or payload.adjusted_total is not None or payload.adjusted_total_incl_tax is not None:
            raise HTTPException(422,'清空价格时不能同时提交单价或金额')
        owner=by_id[key]
        record_order_rates(db,user,project,owner,numbers[key],
                           rates.order_rates(db,owner,owner.language_pair or project.language_pair),[])
        from translation_document_requirements import set_price_default_disabled
        set_price_default_disabled(db,project,key,True,user.id)
        for charge in list(owner.customer_charge_items):owner.customer_charge_items.remove(charge);db.delete(charge)
        owner.updated_at=project.updated_at=business_now().replace(tzinfo=None)
        db.flush();rates.invalidate_metadata(db);quantity_basis.invalidate(db)
        finish_payment()
        audit.append(db,user,project,before)
        return
    if payload.pricing_mode=='fixed':
        if payload.update_library:raise HTTPException(422,'固定收费不能同步为客户参考单价')
        adjustment=getattr(project,'order_total_adjustments',{}).get(key,{})
        if not allow_incomplete and payload.adjusted_total is None and payload.adjusted_total_incl_tax is None and not ({'excl_tax','incl_tax'} & adjustment.keys()):
            raise HTTPException(422,'请填写固定收费的不含税金额或含税金额')
        owner=by_id[key]
        record_order_rates(db,user,project,owner,numbers[key],
                           rates.order_rates(db,owner,owner.language_pair or project.language_pair),[])
        for charge in list(owner.customer_charge_items):owner.customer_charge_items.remove(charge);db.delete(charge)
        moment=business_now().replace(tzinfo=None)
        owner.customer_charge_items.append(TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=project.id if owner is project else None,sub_order_id=None if owner is project else owner.id,sequence_no=1,item_name='翻译费',pricing_mode='fixed',currency=payload.currency,total_excl_tax=payload.adjusted_total,total_incl_tax=payload.adjusted_total_incl_tax,amount_override=payload.adjusted_total,remarks=payload.explanation,billing_month=payload.billing_month,created_at=moment,updated_at=moment))
        owner.updated_at=project.updated_at=moment
        db.flush();
        finish_payment()
        audit.append(db,user,project,before)
        return
    if payload.prices is not None:
        from translation_document_requirements import set_price_default_disabled
        set_price_default_disabled(db,project,key,False,user.id)
        save_prices(db,user,project,by_id,parents,key,payload)
        db.flush();
        finish_payment()
        audit.append(db,user,project,before)
        return
    if payload.amount is None:raise HTTPException(422,'请填写单价')
    old={uid:signature(primary(owner)) for uid,owner in by_id.items()}
    moment=business_now().replace(tzinfo=None)

    def write(owner, explicit=False):
        row=primary(owner)
        if row is None:
            row=TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=project.id if owner is project else None,sub_order_id=None if owner is project else owner.id,
                sequence_no=len(owner.customer_charge_items or [])+1,item_name='翻译费',pricing_mode='metric',created_at=moment)
            owner.customer_charge_items.append(row)
        row.unit_price=row.unit_price_excl_tax=payload.amount
        row.currency=payload.currency;row.metric_type=payload.metric;row.unit_size=payload.unit_size;row.billing_month=payload.billing_month
        row.amount_override=row.total_excl_tax=payload.adjusted_total if explicit else None
        if explicit: row.remarks=payload.explanation.strip()
        row.updated_at=moment;owner.updated_at=moment
        return row
    write(by_id[key],True)
    changed={key}
    for owner in owners:
        uid=str(owner.id);parent=parents.get(uid)
        if parent in changed and (old[uid] is None or old[uid][0] is None or old[uid]==old[parent]):
            write(owner);changed.add(uid)
    project.updated_at=moment
    db.flush()
    finish_payment()
    audit.append(db,user,project,before)


def save(db, user, project_id, payload, *, allow_incomplete=False):
    try:
        _write_finance(db,user,project_id,payload,allow_incomplete=allow_incomplete)
        if payload.document_consistency_review is not None:
            save_document_consistency_review(db, user, project_id, payload.document_consistency_review)
        db.commit()
    except Exception:
        db.rollback()
        db.info.pop('translation_monthly_tax_modes',None)
        db.info.pop('translation_billing_tax_modes',None)
        raise
    rates.invalidate_metadata(db)
    quantity_basis.invalidate(db)
    return read(db,project_id)


def inherit_new_order(db, child):
    """新增下级订单时，继承最近上级的单价；显式收费明细优先。"""
    if child.customer_charge_items: return
    number=child.sub_order_no.rsplit('.',1)[0]
    ancestor=db.query(TranslationSubOrder).filter_by(parent_project_id=child.parent_project_id,sub_order_no=number).first()
    source=primary(ancestor) if ancestor else None
    if source is None:
        root=db.get(TranslationProject,child.parent_project_id)
        source=primary(root) if root else None
    if source is None: return
    moment=business_now().replace(tzinfo=None)
    _,currency,metric,size=signature(source)
    owner=ancestor if ancestor and primary(ancestor) else db.get(TranslationProject,child.parent_project_id)
    entries=rates.order_rates(db,owner,owner.language_pair or '') if rates.ready(db) else []
    choices=set(str(child.language_pair or '').split('；'))
    entries=[entry for entry in entries if not child.language_pair or entry['language_pair'] in choices]
    if entries:
        for index,entry in enumerate(entries):
            tax=entry['tax_prices']
            excl=tax['unit_price_excl_tax']
            incl=tax['unit_price_incl_tax']
            if excl is None and incl is None:
                excl=entry['amount']
            excl=Decimal(excl) if excl is not None else None
            incl=Decimal(incl) if incl is not None else None
            row=TranslationSubOrderChargeItem(
                id=uuid4(),sub_order_id=child.id,sequence_no=index+1,item_name='翻译费',pricing_mode='metric',
                metric_type=quantity_basis.storage_metric(quantity_basis.resolve(getattr(child,'word_count_matrix',{}),entry['metric'])[2]),
                unit_size=Decimal(entry['unit_size']),unit_price=excl,unit_price_excl_tax=excl,unit_price_incl_tax=incl,
                currency=entry['currency'],billing_month=source.billing_month,created_at=moment,updated_at=moment,
            )
            child.customer_charge_items.append(row);db.flush();quantity_basis.store(db,row,entry['metric'],getattr(child,'word_count_matrix',{}));db.add(rates.TranslationChargeDirection(charge_id=row.id,language_pair=entry['language_pair'],reference_id=UUID(entry['reference_id']) if entry['reference_id'] else None,reference_revision=entry['reference_revision']))
        rates.invalidate_metadata(db)
    elif not rates.ready(db):
        excl=source.unit_price_excl_tax
        incl=source.unit_price_incl_tax
        if excl is None and incl is None:
            excl=source.unit_price
        child.customer_charge_items.append(TranslationSubOrderChargeItem(
            id=uuid4(),sub_order_id=child.id,sequence_no=1,item_name='翻译费',pricing_mode='metric',
            metric_type=metric,unit_size=size,unit_price=excl,unit_price_excl_tax=excl,unit_price_incl_tax=incl,
            currency=currency,billing_month=source.billing_month,created_at=moment,updated_at=moment,
        ))


router=APIRouter(prefix='/translation-customer-finance',tags=['translation-customer-finance'])


@router.get('/sub-clients/{sub_client_id}/preferences', dependencies=[Depends(require_any_permission(
    'clients:read','clients:write','projects:read','projects:write','finance:read','finance:write'
))])
def read_sub_client_preferences(sub_client_id:UUID,db:Session=Depends(get_db)):
    return sub_client_finance.read(db,sub_client_id)


@router.put('/sub-clients/{sub_client_id}/preferences', dependencies=[Depends(require_any_permission(
    'clients:write','projects:write','finance:write'
))])
def write_sub_client_preferences(sub_client_id:UUID,payload:sub_client_finance.PreferenceWrite,
                                 db:Session=Depends(get_db),user=Depends(get_current_user)):
    changes=payload.model_dump(exclude={'revision'},exclude_unset=True)
    sub_client_finance.write_preferences(db,sub_client_id,changes,user,payload.revision)
    db.commit()
    return sub_client_finance.read(db,sub_client_id)


@router.get('/sub-clients/{sub_client_id}/settlement-party', dependencies=[Depends(require_any_permission(
    'clients:read','clients:write','projects:read','projects:write','finance:read','finance:write'
))])
def read_sub_client_settlement_party(sub_client_id: UUID,
                                     month: str = Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),
                                     period: int | None = Query(None, ge=1), db: Session = Depends(get_db)):
    child = db.get(SubClient, sub_client_id)
    if child is None:
        raise HTTPException(404, '子客户不存在')
    return {'party': sub_client_finance.read_period_party(db, child, month, period)}


@router.put('/sub-clients/{sub_client_id}/settlement-party', dependencies=[Depends(require_any_permission(
    'clients:write','projects:write','finance:write'
))])
def write_sub_client_settlement_party(sub_client_id: UUID, data: sub_client_finance.PeriodPartyWrite,
                                      db: Session = Depends(get_db), user=Depends(get_current_user)):
    return sub_client_finance.write_period_party(db, sub_client_id, data, user)


@router.put('/project/{project_id}/special-settlement')
def save_special_settlement(project_id:UUID,data:special_settlement.SettingsWrite,db:Session=Depends(get_db),
                            user=Depends(require_permission('projects:write'))):
    client_id=project_statement_client_id(db,project_id)
    if client_id:
        db.query(Client).filter_by(id=client_id).with_for_update().first()
    project=db.query(TranslationProject).filter_by(id=project_id,annotation_migrated_at=None).with_for_update().populate_existing().first()
    if not project:
        raise HTTPException(404,'笔译项目不存在')
    from translation_document_requirements import attach
    attach(db,[project])
    attach_monthly_payment_peers(db, [project])
    if payment_method(project)!='special':
        raise HTTPException(422,'此订单当前未采用特殊结算')
    if project.sub_client_id and project.settlement_party == 'client' and (
        data.tax_mode is not None or data.statement_required is not None
    ):
        raise HTTPException(422,'当前账期采用客户结算设置，请在客户管理修改')
    owners,_,_=hierarchy(project)
    order_ids=[str(owner.id) for owner in owners]
    if str(data.order_id) not in order_ids:
        raise HTTPException(422,'子订单不属于当前订单')
    sync_sub_client_statement = bool(project.sub_client_id and project.settlement_party == 'sub_client'
                                     and data.statement_required is not None)
    if sync_sub_client_statement:
        sub_client_finance.write(db,project.sub_client_id,{'statement_required':data.statement_required},user.id)
        data = data.model_copy(update={'statement_required': None})
    if not sync_sub_client_statement or data.model_dump(exclude={'order_id', 'apply_to_order'}, exclude_none=True):
        special_settlement.save(db,project,order_ids,data,user.id)
    db.commit()
    return {'saved':True}


class StatementProjectPreview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    client_id:UUID
    month:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    order_ids:list[UUID]=Field(max_length=2000)
    months:list[str]|None=Field(default=None,min_length=1,max_length=36)
    mode:Literal['parents','all','children']='children'
    settlement_scope:StatementScope|None=None
    period_number:int|None=Field(default=None,ge=1)
    sub_client_id:UUID|None=None

@router.post('/statement-preview',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def statement_project_preview(data:StatementProjectPreview,db:Session=Depends(get_db)):
    from customer_statements import direction_statement_rows
    from customer_statement_workspace import preview_statement_number, scoped_root_ids
    from statement_project_preview import build
    months=sorted(set(data.months or [data.month]))
    if any(not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',month) for month in months):raise HTTPException(422,'账单月份格式应为YYYY-MM')
    parts=[build(db,data.client_id,month,data.order_ids,data.mode,special=data.settlement_scope=='special',
                 group_directions=False) for month in months]
    result=parts[0];lines={line['line_id']:line for part in parts for line in part['rows']}
    result['rows']=list(lines.values());result['month']='、'.join(months)
    if data.sub_client_id:
        child=db.get(SubClient,data.sub_client_id)
        if child is None or child.parent_client_id!=data.client_id:
            raise HTTPException(422,'子客户不属于当前客户')
        roots={str(uid) for uid, in db.query(TranslationProject.id).filter_by(sub_client_id=data.sub_client_id)}
        result['rows']=[line for line in result['rows'] if line['root_id'] in roots]
        result.update(sub_client_name=child.client_name,sub_client_code=child.sub_client_code)
    if data.settlement_scope:
        allowed=scoped_root_ids(db,{line['root_id'] for line in result['rows']},data.settlement_scope)
        result['rows']=[line for line in result['rows'] if line['root_id'] in allowed]
    if data.period_number:
        projects=crud.get_translation_projects(db,limit=None,field_filters={
            'finance_client_ids':{'value':[str(data.client_id)]},'finance_billing_month':{'value':months},
        })
        attach_monthly_payment_peers(db,projects)
        allowed={str(project.id) for project in projects if project.settlement_period_number==data.period_number}
        result['rows']=[line for line in result['rows'] if line['root_id'] in allowed]
    if not result['rows']:raise HTTPException(422,'当前筛选没有项目，也没有目标月份的待入账任务')
    result['pending']=list(dict.fromkeys(issue for part in parts for issue in part['pending']))
    def format_preview(preview, rows, preview_months, period):
        sums={}
        for line in rows:
            if line.get('counted_in_total',True) and line['subtotal'] is not None:
                sums[line['currency']]=sums.get(line['currency'],Decimal(0))+Decimal(line['subtotal'])
        return {**preview,'totals':{key:str(value.quantize(Decimal('.01'))) for key,value in sums.items()},
                'statement_number':preview_statement_number(db,data.client_id,preview_months,rows,
                    period_number=period,settlement_scope=data.settlement_scope),
                'rows':direction_statement_rows(rows)}

    formatted = format_preview(result,result['rows'],months,data.period_number)
    if any(line.get('sub_client_id') for line in result['rows']):
        from customer_statement_workspace import billing_period_name
        groups={}
        for line in result['rows']:
            sub_id=line.get('sub_client_id')
            key=(sub_id,line['billing_month'],line.get('settlement_period_number')) if sub_id else (None,None,None)
            groups.setdefault(key,[]).append(line)
        previews=[]
        for (sub_id,month,period),rows in groups.items():
            header=result
            if sub_id:
                header={**result,'month':billing_period_name(month,period) if period else month,
                        'sub_client_code':rows[0]['sub_client_code'],'sub_client_name':rows[0]['sub_client_name'],
                        'tax_included':all(line['unit_label']=='含税' for line in rows)}
            previews.append(format_preview(header,rows,[month] if sub_id else months,period if sub_id else data.period_number))
        formatted['settlement_previews']=previews
    return formatted


def matches_missing_fields(node, word_count=False, unit_price=False, total=None):
    """以列表实际展示的母订单汇总值判断，0 是已填值。"""
    if word_count:
        matrix=node.get('word_count_matrix') or {}
        if any(value is not None and value!='' for dimension in ('company','customer') for value in (matrix.get(dimension) or {}).values()):
            return False
    if unit_price:
        if node.get('pricing_mode')=='fixed':
            return False
        prices=[price for price in (node.get('prices') or [{'amount':node.get('amount')}]) if price.get('pricing_mode')!='fixed']
        if not any(price.get('amount') is None and all((price.get('tax_prices') or {}).get(key) is None for key in ('unit_price_excl_tax','unit_price_incl_tax')) for price in prices):
            return False
    if total:
        excl=not node.get('totals_excl_tax')
        incl=not node.get('totals_incl_tax')
        if not {'excl':excl,'incl':incl,'both':excl and incl,'either':excl or incl,'fixed':node.get('pricing_mode')=='fixed' and excl and incl}[total]:
            return False
    return True


def subtotal_nodes(nodes):
    groups={}
    amount_fields=('totals','adjusted_totals','totals_excl_tax','totals_incl_tax','billing_totals')
    for node in nodes:
        key=node.get('client_id') or 'unassigned'
        group=groups.setdefault(key,dict(client_id=key,client_name=node.get('client_short_name') or '-',project_count=0,incomplete=False,**{field:{} for field in amount_fields}))
        group['project_count']+=1
        group['incomplete']|=node['incomplete']
        for field in amount_fields:
            for currency,amount in node.get(field,{}).items():
                group[field][currency]=group[field].get(currency,Decimal(0))+Decimal(amount)
    for group in groups.values():
        for field in amount_fields:group[field]={currency:str(amount) for currency,amount in group[field].items()}
    return sorted(groups.values(),key=lambda group:group['client_name'])


def paginate_child_orders(roots,skip,limit,*,count_parent_orders=False,expand_all_orders=True,order_expansion_ids=()):
    position=0
    display_offset=0

    overrides = {str(order_id) for order_id in order_expansion_ids}

    def select(node,counted):
        nonlocal position,display_offset
        first=position+1
        index=None
        if counted:
            position+=1
            if skip<position<=skip+limit:index=position
        expanded = expand_all_orders != (node['id'] in overrides)
        children=[selected for child in node['children'] if (selected:=select(child,True)) is not None] if expanded else []
        last=min(position,skip)
        if not count_parent_orders and first<=last:
            # Each previous page overlapping this subtree displayed its ancestor row once.
            display_offset+=(last-1)//limit-(first-1)//limit+1
        if index is None and not children:return None
        return dict(id=node['id'],page_index=index,children=children)

    rows=[selected for root in roots if (selected:=select(root,count_parent_orders or not root['children'])) is not None]
    return rows,position,skip if count_parent_orders else display_offset


def apply_order_page(node,selection):
    children={child['id']:child for child in node['children']}
    return {**node,'has_children':bool(children),'page_index':selection['page_index'],
        'children':[apply_order_page(children[child['id']],child) for child in selection['children']]}


@router.get('/page',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def page(skip:int=Query(0,ge=0),limit:int=Query(10,ge=1,le=100),keyword:str|None=None,project_status:str|None=None,billing_month:str|None=Query(None,pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),client:str|None=None,client_manager:str|None=None,client_id:UUID|None=None,db:Session=Depends(get_db),only_mine:bool=False,user=Depends(get_current_user),manager_ids:list[UUID]|None=Query(None,max_length=2000),statement_required:bool|None=None,sort:Literal['client_short_name_asc','client_short_name_desc','client_manager_asc','client_manager_desc']|None=None,missing_word_count:bool=False,missing_unit_price:bool=False,missing_total:Literal['excl','incl','both','either','fixed']|None=None,project_statuses:list[str]|None=Query(None,max_length=100),client_order_count:Literal['single','multiple']|None=None,group_clients:bool=True,selected_client_ids:list[UUID]|None=Query(None,alias='client_ids',max_length=100),payment_status:Literal['unpaid','deposit','mid','full','paid','full_mismatch']|None=None,include_payment_status:bool=False,exclude_full:bool=False,payment_project_id:UUID|None=None,include_invoice_status:bool=False,invoice_status:Literal['unissued','partial','issued','not_required']|None=None,invoice_required:Literal['yes','no','unknown']|None=None,statement_customers:Literal['include','exclude']|None=None,payment_amount_mismatch:bool=False,pricing_mode:Literal['metric','fixed','aggregate']|None=None,billing_months:list[Annotated[str,Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')]]|None=Query(None,max_length=1200),paginate_children:bool=False,count_parent_orders:bool=False,expand_all_orders:bool=True,order_expansion_ids:list[UUID]|None=Query(None), settlement_project_id:UUID|None=None, settlement_scope:StatementScope|None=None,period_number:int|None=Query(None,ge=1),special_invoice_tracking:bool=False,special_invoice_project_id:UUID|None=None, unassigned_period:bool=False, quotation_required:bool|None=None, settlement_mode:SettlementMode|None=None, language_direction:str|None=Query(None,max_length=200), fixed_manager_name:str|None=Query(None,max_length=255),sub_client_id:UUID|None=None,sub_client:str|None=None,statement_presence:Literal['present','absent']|None=None,statement_period_state:Literal['assigned','unassigned']|None=None,statement_board_ids:list[UUID]|None=Query(None,max_length=100),ledger_view:bool=False,ledger_audit:bool=False,word_count_state:Literal['filled','missing']|None=None,unit_price_state:Literal['filled','missing']|None=None,document_type:Literal['quotation','statement','invoice']|None=None,document_requirement:Literal['yes','no','unknown']|None=None,document_presence:Literal['present','absent']|None=None):
    special_invoice_tracking=special_invoice_tracking and settlement_scope=='special'
    filter_amount_mismatch = payment_amount_mismatch or payment_status == 'full_mismatch'
    filter_invoice = invoice_status is not None or invoice_required is not None

    from translation_payment_filters import attach_payment_status, settlement_payment_states
    payment_states={}
    invoice_scope_ids=None
    ledger_summary=None
    def finish(result):
        if ledger_summary is not None:result['ledger_summary']=ledger_summary
        if settlement_scope=='special':
            result['client_subtotals']=original_subtotals
        if include_invoice_status and not special_invoice_tracking:
            from translation_project_invoices import attach
            if settlement_scope=='special':
                def original_invoice(node):
                    node['invoice_required']=node.get('original_invoice_required')
                    for child in node['children']:original_invoice(child)
                for node in result['items']:original_invoice(node)
            attach(db,result)
        if include_invoice_status:
            result['invoice_filter_applied']=True
            if invoice_scope_ids is not None:
                result['merged_invoice_scope']=len(invoice_scope_ids)>1
        if filter_amount_mismatch:result['payment_amount_mismatch_filter_applied']=True
        if include_payment_status:
            return attach_payment_status(db,result,settlement_states=payment_states)
        return result
    if payment_amount_mismatch:
        # 独立核对入口，不叠加左侧月份、客户名称与付款状态。
        billing_month=None;billing_months=None;client=None
    if filter_amount_mismatch:payment_status='full'
    fields={}
    if invoice_status and invoice_status != 'not_required' and settlement_scope!='special':
        fields['finance_invoice_status']={'value':invoice_status}
    if payment_project_id:fields['finance_payment_project_id']={'value':str(payment_project_id)}
    filter_payment=bool(payment_status or exclude_full)
    if client_id: fields['finance_client_id']={'value':str(client_id)}
    if isinstance(selected_client_ids,list):fields['finance_client_ids']={'value':[str(uid) for uid in selected_client_ids]}
    if isinstance(sub_client_id,UUID):fields['finance_sub_client_id']={'value':str(sub_client_id)}
    months=list(dict.fromkeys(billing_months)) if isinstance(billing_months,list) else []
    if months:
        fields['finance_billing_month']={'value':months}
        billing_month=months[0] if len(months)==1 else None
    elif billing_month: fields['finance_billing_month']={'value':billing_month}
    from finance_manager_scope import manager_fields
    fields.update(manager_fields(db,user,manager_ids,only_mine,client_manager))
    if isinstance(fixed_manager_name,str):
        fields['finance_manager_exact']={'value':fixed_manager_name.strip().lower()}
    if client and client.strip(): fields['finance_client']={'value':client.strip()}
    if sub_client and sub_client.strip(): fields['finance_sub_client']={'value':sub_client.strip()}
    invoice_scope=include_invoice_status and settlement_project_id is not None
    if statement_customers is not None and invoice_scope:
        if statement_required is None:
            statement_required=statement_customers=='include'
        statement_client_filter=None
    elif statement_customers is not None:
        if special_invoice_tracking:
            statement_client_filter=None
        else:
            candidates=db.query(TranslationProject).filter(TranslationProject.annotation_migrated_at.is_(None)).all()
            required=effective_statement_requirements(db,candidates)
            statement_client_filter={statement_client_id(project) for project in candidates if required[project.id]} - {None}
    else:
        statement_client_filter=None
    status_values=project_statuses if isinstance(project_statuses,list) else []
    statuses=list(dict.fromkeys(status.strip() for status in status_values if status.strip()))
    if statuses and settlement_scope!='special':fields['project_status']={'value':statuses}
    if invoice_scope:
        source=crud.get_translation_project(db,settlement_project_id)
        if not source:
            raise HTTPException(404,'笔译项目不存在')
        from translation_document_requirements import attach as attach_documents
        attach_documents(db,[source])
        attach_monthly_payment_peers(db,[source])
        invoice_scope_ids={source.id,*(peer.id for peer in monthly_tax_projects(db,source))}
        fields['finance_invoice_project_ids']={'value':invoice_scope_ids}
    filters=dict(keyword=keyword,project_status=None if statuses else project_status,field_filters=fields)
    missing_filters=missing_word_count or missing_unit_price or missing_total is not None
    statement_board_filter={str(uid) for uid in statement_board_ids} if isinstance(statement_board_ids,list) else set()
    all_matches=ledger_view or ledger_audit or bool(word_count_state or unit_price_state or document_type) or bool(statement_board_filter) or statement_presence is not None or statement_period_state is not None or paginate_children or missing_filters or client_order_count is not None or filter_payment or pricing_mode is not None or filter_invoice or statement_required is not None or statement_client_filter is not None or settlement_project_id is not None or settlement_scope is not None or isinstance(period_number,int) or unassigned_period or quotation_required is not None or settlement_mode is not None or isinstance(language_direction,str)
    projects=crud.get_translation_projects(db,skip=0 if all_matches else skip,limit=None if all_matches else limit,sort=sort,finance_only=True,
                                          **({**filters,'keyword':None} if special_invoice_tracking or ledger_view else filters))
    if ledger_view:
        from finance_settlement_ledger import statement_root_ids
        extra_roots=statement_root_ids(db,fields,months or ([billing_month] if billing_month else None))-{str(project.id) for project in projects}
        if extra_roots:
            extra_fields={key:value for key,value in fields.items() if key not in ('finance_billing_month','finance_client','finance_client_id','finance_client_ids')}
            extra_fields['finance_invoice_project_ids']={'value':list(extra_roots)}
            projects.extend(crud.get_translation_projects(db,limit=None,finance_only=True,field_filters=extra_fields))
    if isinstance(language_direction,str):
        from translation_direction_service import stored_directions
        wanted=language_direction.casefold()
        projects=[project for project in projects if any(
            wanted==direction.casefold() for owner in (project,*project.sub_orders)
            for direction in stored_directions(owner.language_pair)
        )]
    if special_invoice_tracking and isinstance(special_invoice_project_id,UUID):
        projects=[project for project in projects if project.id==special_invoice_project_id]
    if statement_client_filter is not None:
        projects=[project for project in projects if (statement_client_id(project) in statement_client_filter)==(statement_customers=='include')]
    attach_monthly_payment_peers(db,projects)
    if settlement_scope is not None:
        projects=[project for project in projects if matches_statement_scope(project,settlement_scope)]
    if isinstance(period_number,int):
        projects=[project for project in projects if project.settlement_period_number==period_number]
    if unassigned_period:
        projects=[project for project in projects if project.settlement_period_number is None]
    if settlement_mode is not None:
        projects=[project for project in projects if payment_method(project)==settlement_mode]
    if invoice_scope:
        from translation_statement_status import attach as attach_statement_status
        for offset in range(0,len(projects),100):
            attach_statement_status(db,projects[offset:offset+100])
    elif settlement_project_id is not None:
        source = crud.get_translation_project(db, settlement_project_id)
        if not source:
            raise HTTPException(404, '笔译项目不存在')
        attach_monthly_payment_peers(db, [source])
        scope = (statement_client_id(source), effective_billing_month(source), source.settlement_period_number)
        projects = [project for project in projects if (
            statement_client_id(project), effective_billing_month(project), project.settlement_period_number
        ) == scope and project.sub_client_id==source.sub_client_id
                    and (not source.sub_client_id or payment_method(project)==payment_method(source))]
    preload_monthly_tax_projects(db, projects)
    ledger_scope_projects=list(projects) if ledger_view else projects
    if include_payment_status or filter_payment:
        payment_states=settlement_payment_states(db,projects)
    if filter_payment:
        wanted={'unpaid','deposit','mid','full'}
        if payment_status=='paid':
            wanted.discard('unpaid')
        elif payment_status:
            wanted={payment_status}
        if exclude_full:
            wanted.discard('full')
        projects=[project for project in projects if payment_states[str(project.id)][1] in wanted]
    load_charge_metadata(db,ledger_scope_projects if ledger_view else projects)
    from translation_statement_status import customer_boards
    client_ids={project.id:(project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)) for project in (ledger_scope_projects if ledger_view else projects)}
    def attach_boards(visible):
        monthly=customer_boards(db,{client_ids[project.id] for project in visible if client_ids[project.id]})
        for project in visible:project.customer_statements=monthly.get(str(client_ids[project.id]),[])

    if not paginate_children:
        attach_boards(ledger_scope_projects if ledger_view else projects)
        load_finance_details(db,ledger_scope_projects if ledger_view else projects)
    else:
        load_finance_details(db, projects, tax_only=True)
    original_subtotals=[]
    if all_matches:
        matched=[tree(project,billing_month,summary_only=paginate_children,include_version=False,
            include_billing_tax_mode=not paginate_children or filter_amount_mismatch or filter_invoice or statement_required is not None)['item'] for project in projects]
        settlement_nodes=list(matched)
        if ledger_view:
            initial={node['id']:node for node in matched}
            settlement_nodes=[initial.get(str(project.id)) or tree(project,billing_month,include_version=False)['item'] for project in ledger_scope_projects]
        if settlement_scope=='special':
            original_subtotals=subtotal_nodes(matched)
            if statuses:
                matched=[node for node in matched if node['project_status'] in statuses]
            settings=special_settlement.settings_by_project(db,[project.id for project in projects])
            if special_invoice_tracking:
                from translation_project_invoices import attach
                from search_matching import matches_keywords
                attach(db,{'items':matched})
            for node in matched:
                special_settlement.apply_settings(node,settings.get(UUID(node['id']),{}))
            if special_invoice_tracking:
                client_names={str(project.id):project.client_name for project in projects}
                if statement_customers is not None:
                    statement_clients={root['client_id'] for root in matched if root['client_id'] and
                                       (root['statement_required'] or root['has_statement_required_orders'])}
                    matched=[root for root in matched if
                             (root['client_id'] in statement_clients)==(statement_customers=='include')]
                invoice_rows=[]
                for root in matched:
                    root_settings=settings.get(UUID(root['id']),{})
                    for node in special_settlement.order_nodes(root):
                        if not matches_keywords(' '.join(filter(None,(node['order_no'],node['project_name'],
                                                node['client_short_name'],client_names.get(root['id'])))),keyword):
                            continue
                        state=special_settlement.invoice_state(root_settings.get(node['id'],{})) if include_invoice_status else {}
                        state.pop('proofs',None)
                        invoice_rows.append({**node,**state,'children':[], 'has_children':bool(node['children']),
                            'special_invoice_totals':special_settlement.billing_totals(node,tax_mode='incl_tax'),
                            'special_excl_totals':special_settlement.billing_totals(node,tax_mode='excl_tax')})
                matched=invoice_rows
        if statement_board_filter:
            matched=[node for node in matched if any(item['board_id'] in statement_board_filter for item in node.get('statement_status',[]))]
        if statement_presence is not None:
            matched=[node for node in matched if bool(node.get('statement_status'))==(statement_presence=='present')]
        if statement_period_state is not None:
            matched=[node for node in matched if bool(node.get('settlement_period_number') or any(item.get('period_number') for item in node.get('statement_status',[])))==(statement_period_state=='assigned')]
        if statement_required is not None:
            matched=[node for node in matched if (node['statement_required'] or node.get('has_statement_required_orders',False)) is statement_required]
        if quotation_required is not None:
            matched=[node for node in matched if node['quotation_required'] is quotation_required]
        matched=[node for node in matched if matches_missing_fields(node,missing_word_count,missing_unit_price,missing_total)]
        if pricing_mode is not None:matched=[node for node in matched if node.get('pricing_mode')==pricing_mode]
        if filter_invoice:
            from translation_project_invoices import invoice_required as order_requires_invoice
            expected = {'yes': True, 'no': False, 'unknown': None}
            filtered = []
            for node in matched:
                required = node['invoice_required'] if settlement_scope=='special' else order_requires_invoice(node)
                if invoice_required is not None and required is not expected[invoice_required]:
                    continue
                if invoice_status is not None and (required is False) != (invoice_status == 'not_required'):
                    continue
                if settlement_scope=='special' and invoice_status not in (None,'not_required',node['special_invoice_status']):
                    continue
                filtered.append(node)
            matched = filtered
        if ledger_audit or word_count_state or unit_price_state or document_type:
            from finance_ledger_audit import filter_rows,summary
            from translation_project_invoices import attach as attach_invoices
            attach_invoices(db,{'items':matched})
            matched=filter_rows(matched,word_count_state=word_count_state,unit_price_state=unit_price_state,document_type=document_type,document_requirement=document_requirement,document_presence=document_presence)
            if ledger_audit:ledger_summary=summary(matched)
        if filter_amount_mismatch:
            attach_payment_status(db,{'items':matched},settlement_states=payment_states)
            matched=[node for node in matched if node['payment_status']=='full' and node['payment_amount_mismatch']]
        if ledger_view:
            from finance_settlement_ledger import build as build_ledger
            if include_payment_status:attach_payment_status(db,{'items':settlement_nodes},settlement_states=payment_states)
            from translation_project_invoices import attach as attach_ledger_invoices
            attach_ledger_invoices(db,{'items':settlement_nodes})
            for node in settlement_nodes:
                if node['id'] in payment_states:node['ledger_payment_source_id']=str(payment_states[node['id']][0])
            units,settlement_summary=build_ledger(db,settlement_nodes,matched,months=billing_months or ([billing_month] if billing_month else None))
            if keyword:
                from search_matching import matches_keywords
                units=[unit for unit in units if matches_keywords(' '.join([unit['ledger_label'],unit.get('client_short_name') or '',*[str(row.get('order_no',''))+' '+str(row.get('project_name','')) for row in unit['ledger_orders']]]),keyword)]
                from finance_settlement_ledger import settlement_summary as summarize_units
                settlement_summary=summarize_units(units)
                if ledger_audit:
                    selected_roots={root for unit in units for root in unit['ledger_root_ids']}
                    ledger_summary=summary([node for node in matched if node['id'] in selected_roots])
            if sort:
                field='client_manager' if sort.startswith('client_manager') else 'client_short_name'
                units.sort(key=lambda unit:((unit.get(field) or '').casefold(),unit['ledger_label']),reverse=sort.endswith('_desc'))
            return {'items':units[skip:skip+limit],'total':len(units),'settlement_units':True,
                    'ledger_summary':ledger_summary,'settlement_summary':settlement_summary,
                    'invoice_filter_applied':include_invoice_status,'payment_amount_mismatch_filter_applied':filter_amount_mismatch}
        if client_order_count:
            owners={str(project.id):project for project in projects}
            groups={}
            for node in matched:
                owner=owners[node['id']]
                identity=node.get('client_id') or ('name:'+owner.client_name.strip().casefold() if owner.client_name and owner.client_name.strip() else 'unlinked:'+node['id'])
                node['client_group_key']=identity
                groups.setdefault(identity,[]).append(node)
            groups={key:values for key,values in groups.items() if (len(values)==1 if client_order_count=='single' else len(values)>1)}
            filtered=[node for values in groups.values() for node in values]
            if client_order_count=='multiple' and group_clients and not paginate_children:
                ordered=list(groups.items()) if sort else sorted(groups.items(),key=lambda pair:((pair[1][0].get('client_short_name') or '').casefold(),pair[0]))
                selected=ordered[skip:skip+limit]
                return finish({'items':[node for _,values in selected for node in values],'total':len(ordered),'order_total':len(filtered),'pagination_unit':'clients','client_subtotals':subtotal_nodes(filtered),'client_groups':[{'key':key,'name':values[0].get('client_short_name') or '未关联客户','count':len(values)} for key,values in selected]})
            matched=filtered
        if paginate_children:
            selected,total,display_offset=paginate_child_orders(matched,skip,limit,count_parent_orders=count_parent_orders,
                expand_all_orders=expand_all_orders,order_expansion_ids=order_expansion_ids if isinstance(order_expansion_ids,list) else ())
            by_id={str(project.id):project for project in projects}
            visible = [by_id[row['id']] for row in selected]
            attach_boards(visible)
            load_finance_details(db, visible)
            items=[apply_order_page(tree(by_id[row['id']],billing_month,include_version=False)['item'],row) for row in selected]
            return finish({'items':items,'total':total,'pagination_unit':'child_orders','display_offset':display_offset,'client_subtotals':subtotal_nodes(matched)})
        if special_invoice_tracking:
            return finish({'items':matched[skip:skip+limit],'total':len(matched)})
        return finish({'items':matched[skip:skip+limit],'total':len(matched),'client_subtotals':subtotal_nodes(matched)})
    return finish({'items':[tree(project,billing_month,include_version=False)['item'] for project in projects],'total':crud.count_translation_projects(db,**filters),'client_subtotals':client_subtotals(db,filters)})



@router.get('/manager-options',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def manager_options(db:Session=Depends(get_db)):
    from organization_service import department_condition
    people=db.query(AppUser).filter(AppUser.is_deleted.is_(False),department_condition(db,['客户部'])).order_by(AppUser.full_name,AppUser.username,AppUser.id).all()
    return {'items':[{'id':str(person.id),'name':person.full_name or person.username,'username':person.username,'active':bool(person.is_active)} for person in people]}


@router.get('/row-filter-options',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def row_filter_options(billing_month:str|None=Query(None,pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),
                       manager_ids:list[UUID]|None=Query(None,max_length=2000),only_mine:bool=False,
                       client_id:UUID|None=None,client_ids:list[UUID]|None=Query(None,max_length=100),
                       db:Session=Depends(get_db),user=Depends(get_current_user)):
    from finance_manager_scope import manager_fields
    from statement_customer_groups import project_query
    from translation_direction_service import stored_directions

    customer=func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)
    query=project_query(db,billing_month,manager_fields(db,user,manager_ids,only_mine,None))
    if client_id:
        query=query.filter(customer==client_id)
    if client_ids:
        query=query.filter(customer.in_(client_ids))
    orders=query.with_entities(TranslationProject.id.label('order_id'),customer.label('customer_id'),
                               TranslationProject.language_pair.label('direction')).subquery()
    clients=db.query(Client).filter(Client.id.in_(db.query(orders.c.customer_id))).order_by(
        Client.client_short_name,Client.client_name,Client.id,
    ).all()
    root_directions=db.query(orders.c.direction).distinct()
    child_directions=db.query(TranslationSubOrder.language_pair).filter(
        TranslationSubOrder.parent_project_id.in_(db.query(orders.c.order_id)),
    ).distinct()
    directions=sorted({pair for values in (root_directions,child_directions) for (value,) in values
                       for pair in stored_directions(value)})
    return {'clients':[{'id':str(client.id),'name':client.client_short_name or client.client_name,'code':client.client_code}
                       for client in clients],'directions':directions}


class StatementRequiredWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    statement_required:bool
    expected_statement_required:bool
    expected_updated_at:datetime|None=None
    copy_to_same_month:bool=False
    statement_sync: StatementSyncScope | None = None
    statement_customer_sync: StatementCustomerSync | None = None
    billing_month:str|None=Field(default=None,pattern=r'^\d{4}-(0[1-9]|1[0-2])$')


@router.get('/statement-requirement-context', dependencies=[Depends(require_permission('projects:read'))])
def statement_requirement_context(
    project_id: UUID | None = None,
    client_id: UUID | None = None,
    billing_month: str | None = Query(None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    from customer_statements import client_preference

    if project_id:
        project = db.query(TranslationProject).filter_by(id=project_id, annotation_migrated_at=None).first()
        if project is None:
            raise HTTPException(404, '笔译项目不存在')
        client_id, billing_month = statement_client_id(project), effective_billing_month(project)
    preference = client_preference(db, client_id) if client_id else {'statement_default': 'unknown', 'revision': 0}
    other_count = 0
    if client_id and billing_month:
        projects = statement_month_projects(db, client_id, billing_month)
        if project_id:
            projects = projects.filter(TranslationProject.id != project_id)
        other_count = projects.count()
    return dict(statement_default=preference['statement_default'], payment_method=preference.get('payment_method'), client_id=client_id,
                billing_month=billing_month, other_count=other_count, preference_revision=preference['revision'],
                can_update_customer=bool(client_id and user_has_permission(db, user.id, 'clients:write')))


@router.put('/project/{project_id}/statement-required',dependencies=[Depends(require_permission('projects:write'))])
def update_statement_required(project_id:UUID,payload:StatementRequiredWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):
    import translation_document_requirements as documents
    locked_client=project_statement_client_id(db,project_id)
    if locked_client:db.query(Client).filter_by(id=locked_client).with_for_update().first()
    project=db.query(TranslationProject).filter(TranslationProject.id==project_id,TranslationProject.annotation_migrated_at.is_(None)).with_for_update().populate_existing().first()
    if project is None:raise HTTPException(404,'笔译项目不存在')
    from concurrency import assert_fresh, StaleUpdateError
    try:assert_fresh(project,payload.expected_updated_at)
    except StaleUpdateError:raise HTTPException(409,'项目已被其他人修改，请刷新后重试')
    crud._attach_project_client_fields(project)
    from translation_customer_type import attach as attach_customer_types
    attach_customer_types(db,[project])
    documents.attach(db,[project])
    attach_monthly_payment_peers(db,[project])
    before=bool(project.statement_required)
    # 保存前值必须与价格与付款窗口的 GET 响应一致。单独 attach 只处理
    # 客户类型/单据默认值，尚未应用客户结算主体和已有账单归属。
    # 两套推导结果不能作为彼此的乐观锁基线，否则未发生修改也会误报 409。
    current=read(db,project.id)['item']
    if project.sub_client_id and project.settlement_party != 'client':
        if current['statement_required'] != payload.expected_statement_required:
            raise HTTPException(409,'子客户对账单设置已更新，请刷新后重试')
        sub_client_finance.write(db,project.sub_client_id,{'statement_required':payload.statement_required},user.id)
        db.commit()
        return {'id':str(project.id),'statement_required':payload.statement_required,'payment_method':payment_method(project),
                'updated_at':business_datetime(project.updated_at).isoformat() if project.updated_at else None,
                'affected_count':1}
    effective_before=bool(current['statement_required'])
    previous_updated_at=business_datetime(project.updated_at).isoformat() if project.updated_at else None
    if effective_before!=payload.expected_statement_required:raise HTTPException(409,'是否需对账单的当前设置已变化，请重新打开价格与付款后重试')
    try:
        scope = payload.statement_sync
        if payload.copy_to_same_month:
            if not payload.billing_month or effective_billing_month(project) != payload.billing_month:
                raise HTTPException(422, '同步对账单设置时必须指定当前订单所属账单月份')
            client_id = statement_client_id(project)
            if not client_id:
                raise HTTPException(422, '请先为当前项目关联客户')
            scope = StatementSyncScope(client_id=client_id, billing_month=payload.billing_month)
        changed = 0
        if scope:
            if scope.client_id != locked_client:
                raise HTTPException(409, '项目客户已变化，请重新确认同步范围')
            changed = sync_statement_month(db, project, scope, payload.statement_required, user.id)
        if before != payload.statement_required or not project.statement_required_explicit:
            from customer_statements import record_order_documents
            record_order_documents(db,user,project,locked_client,statement_default=payload.statement_required)
            documents.save(db, project, statement_required=payload.statement_required, actor_id=user.id)
            project.updated_at = business_now().replace(tzinfo=None)
            changed += 1
        from customer_statements import auto_sync_document_defaults
        if payload.statement_customer_sync:
            sync_statement_customer(db, project, payload.statement_customer_sync, payload.statement_required, user, locked_client)
        auto_sync_document_defaults(db,user,locked_client,statement_default='required' if payload.statement_required else 'not_required')
        if changed or payload.statement_customer_sync:
            db.commit()
        project.statement_required = payload.statement_required
        attach_monthly_payment_peers(db, [project])
        return {'id':str(project.id),'statement_required':payload.statement_required,'payment_method':payment_method(project),'updated_at':business_datetime(project.updated_at).isoformat() if project.updated_at else None,'previous_updated_at':previous_updated_at,'affected_count':changed}
    except Exception:
        db.rollback();raise


@router.get('/statement-customer-groups',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def statement_customer_groups(billing_month:str=Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),statement_required:bool=True,keyword:str|None=None,skip:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),manager_ids:list[UUID]|None=Query(None,max_length=2000),only_mine:bool=False,client_manager:str|None=None,db:Session=Depends(get_db),user=Depends(get_current_user),progress:Progress|None=None,settlement_scope:StatementScope|None=None,period_number:int|None=Query(None,ge=1),special_invoice_tracking:bool=False,special_invoice_project_id:UUID|None=None):
    from statement_customer_groups import customers
    from finance_manager_scope import manager_fields
    return customers(db,billing_month,statement_required,keyword,skip,limit,manager_fields(db,user,manager_ids,only_mine,client_manager),progress,settlement_scope,period_number if isinstance(period_number,int) else None)


@router.put('/statement-customer-groups/{client_id}',dependencies=[Depends(require_permission('projects:write'))])
def move_statement_customer(client_id:UUID,payload:CustomerGroupMove,db:Session=Depends(get_db),user=Depends(get_current_user)):
    from statement_customer_groups import move
    return move(db,user,client_id,payload)


@router.get('/statement-customers',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def statement_customers(keyword:str|None=None,required_only:bool=True,skip:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100),db:Session=Depends(get_db),
                        include_sub_clients:bool=False):
    from sqlalchemy import or_, select
    from search_matching import keyword_any
    import translation_document_requirements as documents
    from customer_statement_workspace import StatementWorkspace
    if required_only and not documents.ready(db):
        raise HTTPException(503,'项目单据存储尚未初始化')
    candidates = documents.statement_customer_ids(db, required_only=False)
    if required_only:
        projects=db.query(TranslationProject).filter(TranslationProject.annotation_migrated_at.is_(None)).all()
        requirements=effective_statement_requirements(db,projects)
        candidates={statement_client_id(project) for project in projects if requirements[project.id]} - {None}
    query=db.query(Client).filter(Client.id.in_(candidates))
    if not required_only:
        from sqlalchemy import inspect
        if inspect(db.connection()).has_table(StatementWorkspace.__tablename__):
            query=db.query(Client).filter(or_(Client.id.in_(candidates),Client.id.in_(select(StatementWorkspace.client_id))))
    if include_sub_clients:
        from sqlalchemy import literal
        parents=query.with_entities(Client.id.label('id'),Client.client_name.label('name'),
            Client.client_short_name.label('short_name'),Client.client_code.label('code'),
            literal(None).label('parent_name'))
        children=db.query(SubClient.id.label('id'),SubClient.client_name.label('name'),
            SubClient.client_short_name.label('short_name'),SubClient.sub_client_code.label('code'),
            Client.client_short_name.label('parent_name')).join(Client,Client.id==SubClient.parent_client_id).filter(
                SubClient.parent_client_id.in_(query.with_entities(Client.id).statement))
        if keyword and keyword.strip():
            parents=parents.filter(keyword_any([Client.client_name,Client.client_short_name,Client.client_code],keyword))
            children=children.filter(keyword_any([Client.client_name,Client.client_short_name,Client.client_code,
                SubClient.client_name,SubClient.client_short_name,SubClient.sub_client_code],keyword))
        options=parents.union_all(children).subquery()
        matches=db.query(options)
        return {'items':[dict(row._mapping) for row in matches.order_by(
            func.coalesce(options.c.parent_name,options.c.short_name),options.c.parent_name.is_not(None),
            options.c.short_name,options.c.id).offset(skip).limit(limit)],'total':matches.count()}
    if keyword and keyword.strip():query=query.filter(keyword_any([Client.client_name,Client.client_short_name,Client.client_code],keyword.strip()))
    total=query.count()
    return {'items':[{'id':str(client.id),'name':client.client_name or client.client_short_name,'short_name':client.client_short_name or client.client_name,'code':client.client_code or ''} for client in query.order_by(Client.client_short_name,Client.client_name,Client.id).offset(skip).limit(limit).all()],'total':total}


@router.get('/project/{project_id}',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def detail(project_id:UUID,db:Session=Depends(get_db),special_invoice:bool=False):
    result=read(db,project_id)
    if special_invoice:
        from translation_project_invoices import special_order
        settings=special_settlement.settings_by_project(db,[project_id]).get(project_id,{})
        special_order(result['item'],settings,project_id)
    return result


@router.get('/project/{project_id}/payment-summary', dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def read_payment_summary(project_id: UUID, method: PaymentMethod, db: Session = Depends(get_db)):
    project = crud.get_translation_project(db, project_id)
    if not project:
        raise HTTPException(404, '笔译项目不存在')
    return payment_summary(db, project, method, include_orders=True)


@router.get('/project/{project_id}/sub-client-period-projects', dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def read_sub_client_period_projects(project_id: UUID, db: Session = Depends(get_db)):
    project = crud.get_translation_project(db, project_id)
    if project is None:
        raise HTTPException(404, '笔译项目不存在')
    client_id, month = statement_client_id(project), effective_billing_month(project)
    if not (client_id and project.sub_client_id and month):
        return {'month': month, 'period': None, 'items': []}
    candidates = settlement_candidates(db, {(client_id, month)})
    source = next((row for row in candidates if row[0] == project_id), None)
    period = source[3] if source else None
    ids = {project_id}
    if source:
        ids.update(row[0] for row in candidates if row[3] == period and row[-1] == project.sub_client_id)
    orders = db.query(TranslationProject.id, TranslationProject.order_no, TranslationProject.project_name,
                      TranslationProject.source_file_name).filter(TranslationProject.id.in_(ids)).order_by(
        TranslationProject.order_no, TranslationProject.id,
    )
    return {'month': month, 'period': period if isinstance(period, int) else None,
            'items': [{'id': str(order.id), 'order_no': order.order_no,
                       'project_name': order.source_file_name or order.project_name} for order in orders]}


@router.get('/project/{project_id}/history',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def price_history(project_id:UUID,order_id:UUID|None=None,page:int=Query(1,ge=1),db:Session=Depends(get_db)):
    if not db.get(TranslationProject,project_id):raise HTTPException(404,'笔译项目不存在')
    return audit.history(db,project_id,order_id,page)


@router.put('/project/{project_id}',dependencies=[Depends(require_permission('projects:write'))])
def update(project_id:UUID,payload:PriceWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):
    project=crud.get_translation_project(db,project_id)
    order_key=str(payload.order_id)
    if project and order_key in hierarchy(project)[2].values() and not (
        payload.documents_only or payload.order_pricing_mode in ('aggregate','fixed')
        or (payload.pricing_mode=='fixed' and order_pricing_modes(db,project).get(order_key)=='fixed')
    ):
        raise HTTPException(422,'有子订单的订单只能选择子订单汇总或固定收费')
    attempts=2 if payload.payment_draft is not None or payload.payment_confirmation is not None else 1
    for attempt in range(attempts):
        try:
            _write_finance(db,user,project_id,payload)
            if payload.document_consistency_review is not None:
                save_document_consistency_review(db, user, project_id, payload.document_consistency_review)
            db.commit()
            break
        except OperationalError as error:
            db.rollback()
            if getattr(error.orig,'pgcode',None)!='55P03':
                raise
            rates.invalidate_metadata(db)
            quantity_basis.invalidate(db)
            if attempt+1==attempts:
                raise HTTPException(409,'数据库正在处理其他修改，当前填写已保留，请稍后重新保存') from error
        except Exception:
            db.rollback()
            db.info.pop('translation_monthly_tax_modes',None)
            db.info.pop('translation_billing_tax_modes',None)
            raise
    rates.invalidate_metadata(db)
    quantity_basis.invalidate(db)
    return read(db,project_id)


class TableRateDraft(rates.RateInput):
    amount: Decimal | None = Field(default=None,ge=0,max_digits=14,decimal_places=4)


class TablePriceWrite(PriceWrite):
    prices: list[TableRateDraft] | None = Field(default=None,min_length=1,max_length=100)


class TablePatch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    record_initial_finance:bool=False
    version:str
    document_consistency_review:DocumentConsistencyReview|None=None
    billing_tax_mode:Literal['excl_tax','incl_tax']|None=None
    order_id:UUID
    pricing_mode:Literal['metric','fixed','aggregate']|None=None
    currency:str|None=Field(default=None,pattern=r'^[A-Z]{3}$')
    prices:list[TableRateDraft]|None=Field(default=None,max_length=100)
    adjusted_total:Decimal|None=Field(default=None,ge=0,max_digits=14,decimal_places=2)
    adjusted_total_incl_tax:Decimal|None=Field(default=None,ge=0,max_digits=14,decimal_places=2)
    total_adjustment:OrderTotalAdjustment|None=None
    billing_month:str|None=Field(default=None,pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    explanation:str=Field(default='',max_length=5000)
    customer_explanation:str=Field(default='',max_length=5000)


def save_table_cell(db,user,project_id,payload):
    changes=payload.model_dump(exclude_unset=True,exclude={'version','order_id','document_consistency_review','record_initial_finance'})
    review = {'document_consistency_review': payload.document_consistency_review} if payload.document_consistency_review is not None else {}
    if not changes:raise HTTPException(422,'没有需要保存的字段')
    guard=crud.get_translation_project(db,project_id)
    order_key=str(payload.order_id)
    has_children=bool(guard and order_key in hierarchy(guard)[2].values())
    direct=bool(guard and order_pricing_modes(db,guard).get(order_key)=='fixed')
    requested_mode=changes.get('pricing_mode')
    if 'total_adjustment' in changes:
        if payload.total_adjustment is None or not payload.total_adjustment.model_fields_set:
            raise HTTPException(422,'请选择要调整的折扣或金额')
        if set(changes) <= {'total_adjustment','explanation','customer_explanation'}:
            return save(db,user,project_id,TablePriceWrite(version=payload.version,order_id=payload.order_id,
                        documents_only=True,**changes,**review),allow_incomplete=True)
    if 'billing_tax_mode' in changes and set(changes) <= {'billing_tax_mode','explanation','customer_explanation'}:
        return save(db,user,project_id,TablePriceWrite(
            version=payload.version,order_id=payload.order_id,documents_only=True,**changes,**review,
        ),allow_incomplete=True)
    if has_children and requested_mode=='metric':
        raise HTTPException(422,'有子订单的订单只能选择子订单汇总或固定收费')
    if requested_mode=='aggregate':
        if not has_children or set(changes)!={'pricing_mode'}:
            raise HTTPException(422,'子订单汇总须单独选择，且订单必须有下级')
        return save(db,user,project_id,TablePriceWrite(version=payload.version,order_id=payload.order_id,
                    order_pricing_mode='aggregate',documents_only=True,**review),allow_incomplete=True)
    if has_children and not direct and not requested_mode and any(field not in {'explanation','customer_explanation'} for field in changes):
        raise HTTPException(422,'子订单汇总模式下，请在子订单编辑收费')
    if any(key in changes and changes[key] is None for key in ('pricing_mode','currency','prices')):
        raise HTTPException(422,'计价模式、货币和单价明细不能为 null')
    if changes.get('prices') or 'pricing_mode' in changes:
        current=read(db,project_id)
        def find(node):
            if node['id']==str(payload.order_id):return node
            return next((found for child in node['children'] if (found:=find(child))),None)
        node=find(current['item'])
        if not node:raise HTTPException(422,'订单不属于该笔译项目')
        values={key:node.get(key) for key in ('pricing_mode','currency','adjusted_total','adjusted_total_incl_tax','billing_month','explanation')}
        # 状态切换不把原有的一口价误当成另一计价模式的调整额。
        if 'pricing_mode' in changes and changes['pricing_mode']!=node['pricing_mode']:
            values.update(adjusted_total=None,adjusted_total_incl_tax=None,billing_tax_mode=None)
        values.update(changes)
        if has_children and requested_mode:
            values['order_pricing_mode']=requested_mode
        if values['pricing_mode']=='metric':
            if 'prices' not in changes:
                keys=set(TableRateDraft.model_fields)
                existing_prices=[] if node.get('price_aggregate') else node['prices']
                values['prices']=[{key:value for key,value in price.items() if key in keys} for price in existing_prices] or [
                    dict(language_pair=direction,metric='customer_auto',amount=None)
                    for direction in str(node['language_pair'] or '').split('；') if direction]
            if not values['prices']:
                if not requested_mode:raise HTTPException(422,'请先填写订单的翻译方向')
                values.update(prices=None,clear_finance=True)
        else:values['prices']=None
        return save(db,user,project_id,TablePriceWrite(version=payload.version,order_id=payload.order_id,
                    record_initial_finance=payload.record_initial_finance,**values,**review),allow_incomplete=True)

    audit.require_ready(db)
    client_id=project_statement_client_id(db,project_id)
    if client_id:db.query(Client).filter_by(id=client_id).with_for_update().populate_existing().first()
    project=db.query(TranslationProject).filter_by(id=project_id).filter(TranslationProject.annotation_migrated_at.is_(None)).with_for_update().populate_existing().first()
    if not project:raise HTTPException(404,'笔译项目不存在')
    db.query(TranslationSubOrder).filter_by(parent_project_id=project_id).order_by(TranslationSubOrder.id).with_for_update().populate_existing().all()
    project=crud.get_translation_project(db,project_id)
    if version(project)!=payload.version:raise HTTPException(409,'订单财务已变化，请刷新后重试')
    if 'billing_month' in changes and effective_billing_month(project):changes['billing_month']=effective_billing_month(project)
    owners,_,parents=hierarchy(project)
    owner=next((item for item in owners if item.id==payload.order_id),None)
    if owner is None:raise HTTPException(422,'订单不属于该笔译项目')
    if inherits_fixed_pricing(project, parents, str(owner.id)) and set(changes)-{'explanation','customer_explanation'}:
        raise HTTPException(422,'该订单继承上级固定收费，请在上级订单调整计价方式及金额')
    before=audit.capture(project)
    affected_tax_peers = []
    if 'billing_tax_mode' in changes:
        attach_monthly_payment_peers(db,[project])
        affected_tax_peers = save_settlement_tax(db,user,project,owner,changes.pop('billing_tax_mode'))
    if changes.pop('total_adjustment', None) is not None:
        write_total_adjustment(db,user,project,order_key,payload.total_adjustment,changes.get('currency'))
    elif 'currency' in changes and order_key in getattr(project,'order_total_adjustments',{}):
        save_order_total_adjustment(db,project,order_key,{},changes['currency'],user.id)
    if not changes:
        db.flush();audit.append(db,user,project,before);db.commit();return read(db,project_id)
    if set(changes)<={'explanation','customer_explanation'}:
        finance_notes.apply(db,user,project,owner,internal=changes.get('explanation'),customer=changes.get('customer_explanation'))
        db.flush();audit.append(db,user,project,before);db.commit();return read(db,project_id)
    if 'customer_explanation' in changes:finance_notes.apply(db,user,project,owner,customer=changes.pop('customer_explanation'))
    row=primary(owner)
    moment=business_now().replace(tzinfo=None)
    if 'prices' in changes:
        changes.pop('prices')
        if row and row.pricing_mode=='fixed':raise HTTPException(422,'固定收费不涉及单价')
        record_order_rates(db,user,project,owner,hierarchy(project)[1][str(owner.id)],
                           rates.order_rates(db,owner,owner.language_pair or project.language_pair),[])
        retained={key:getattr(row,key) if row is not None else None for key in ('currency','billing_month','remarks','total_excl_tax','total_incl_tax','amount_override')}
        for old in list(owner.customer_charge_items):
            if quantity_basis.ready(db):
                basis=db.get(quantity_basis.TranslationChargeQuantityBasis,old.id)
                if basis:db.delete(basis)
            meta=db.get(rates.TranslationChargeDirection,old.id)
            if meta:db.delete(meta)
            owner.customer_charge_items.remove(old);db.delete(old)
        row=TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=project.id if owner is project else None,sub_order_id=None if owner is project else owner.id,sequence_no=1,item_name='财务信息',pricing_mode='metric',metric_type='words',unit_size=1,created_at=moment,**{**retained,'currency':retained['currency'] or 'CNY'})
        owner.customer_charge_items.append(row)
        rates.invalidate_metadata(db);quantity_basis.invalidate(db)
    if row is None:
        pending=[tree(project)['item']]
        effective=None
        while pending:
            candidate=pending.pop()
            if candidate['id']==str(owner.id):effective=candidate;break
            pending.extend(candidate['children'])
        if effective and effective['prices']:
            # 子订单备注等修改不能用空收费行遮蔽已经继承的单价。
            rate_keys=set(TableRateDraft.model_fields)
            values={key:effective.get(key) for key in ('currency','adjusted_total','adjusted_total_incl_tax','billing_month','explanation')}
            values.update(changes)
            values['prices']=[{key:value for key,value in price.items() if key in rate_keys} for price in effective['prices']]
            merged=TablePriceWrite(version=payload.version,order_id=payload.order_id,**values)
            save_prices(db,user,project,{str(item.id):item for item in owners},parents,str(owner.id),merged)
            db.flush();confirmations.recheck_after_fee_change(db,project.id,user.id);finish_settlement_tax(db,user,affected_tax_peers);audit.append(db,user,project,before);db.commit()
            return read(db,project_id)
        row=TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=project.id if owner is project else None,sub_order_id=None if owner is project else owner.id,sequence_no=1,item_name='财务信息',pricing_mode='metric',currency='CNY',metric_type='words',unit_size=1,created_at=moment)
        owner.customer_charge_items.append(row)
    if 'adjusted_total' in changes and changes['adjusted_total'] is not None and len({item.currency for item in owner.customer_charge_items})>1:
        raise HTTPException(422,'存在多个币种时请分别在下级订单调整金额')
    mapping={'adjusted_total':'total_excl_tax','adjusted_total_incl_tax':'total_incl_tax','explanation':'remarks','billing_month':'billing_month','currency':'currency'}
    for key,value in changes.items():
        targets=owner.customer_charge_items if key in {'billing_month','explanation'} else [row]
        for target in targets:setattr(target,mapping[key],value);target.updated_at=moment
        if key=='adjusted_total':row.amount_override=value
    row.updated_at=owner.updated_at=project.updated_at=moment
    db.flush();confirmations.recheck_after_fee_change(db,project.id,user.id);finish_settlement_tax(db,user,affected_tax_peers);audit.append(db,user,project,before);db.commit()
    return read(db,project_id)


@router.patch('/project/{project_id}/table',dependencies=[Depends(require_permission('projects:write'))])
def update_table(project_id:UUID,payload:TablePatch,db:Session=Depends(get_db),user=Depends(get_current_user)):
    try:return save_table_cell(db,user,project_id,payload)
    except Exception:
        db.rollback();raise

@router.get('/statement-customer-groups/{client_id}/progress',dependencies=[Depends(require_module_access('projects:read','projects:write'))])
def get_statement_progress(client_id:UUID,billing_month:str=Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),
                           manager_ids:list[UUID]|None=Query(None,max_length=2000),only_mine:bool=False,client_manager:str|None=None,
                           db:Session=Depends(get_db),user=Depends(get_current_user)):
    from customer_statement_progress import read
    return read(db,user,client_id,billing_month,manager_ids,only_mine,client_manager)


@router.put('/statement-customer-groups/{client_id}/progress',dependencies=[Depends(require_permission('projects:write'))])
def set_statement_progress(client_id:UUID,payload:ProgressWrite,db:Session=Depends(get_db),user=Depends(get_current_user)):
    from customer_statement_progress import write
    return write(db,user,client_id,payload)


@router.get('/project/{project_id}/invoice',dependencies=[Depends(require_any_permission('projects:read','finance:read','clients:read','clients:write'))])
def read_invoice(project_id:UUID,order_id:UUID|None=None,db:Session=Depends(get_db),user=Depends(get_current_user),special:bool=False):
    from translation_project_invoices import read
    from invoice_workflow import pending_invoice_requests
    return {**read(db,project_id,order_id,special=special),
            'can_notify_requester':bool(pending_invoice_requests(db,order_id if special and order_id else project_id,user,special=special))}


@router.get('/project/{project_id}/invoice-scope', dependencies=[Depends(require_any_permission(
    'projects:read','projects:write','finance:read','finance:write','clients:read','clients:write'
))])
def invoice_scope(project_id: UUID, db: Session = Depends(get_db)):
    from invoice_workflow import selected_incl_totals
    from translation_document_requirements import attach as attach_documents
    from translation_project_invoices import attach as attach_invoices
    from translation_price_rollup import price_details

    source = crud.get_translation_project(db, project_id)
    if source is None:
        raise HTTPException(404, '笔译项目不存在')
    attach_documents(db, [source])
    attach_monthly_payment_peers(db, [source])
    if payment_method(source) == 'special':
        return {'merged': False, 'items': []}
    peers = monthly_tax_projects(db, source) or [source]
    # Monthly membership is queried separately from the data required to build the finance tree.
    projects = crud.get_translation_projects(db, limit=None, field_filters={
        'finance_invoice_project_ids': {'value': {peer.id for peer in peers}},
    })
    attach_monthly_payment_peers(db, projects)
    load_finance_details(db, projects, tax_only=True)
    roots = [tree(project, summary_only=True, include_version=False)['item'] for project in projects]
    attach_invoices(db, {'items': roots})
    totals = {}
    items = []
    for node in sorted(roots, key=lambda item: item['order_no']):
        invoice_totals = selected_incl_totals(node) if node['invoice_required'] is True else {}
        for currency, amount in invoice_totals.items():
            totals[currency] = totals.get(currency, Decimal(0)) + amount
        items.append({
            'id': node['id'], 'order_no': node['order_no'], 'project_name': node['project_name'],
            'invoice_required': node['invoice_required'], 'invoice_status': node['invoice_status'],
            'billing_totals': node['billing_totals'], 'invoice_totals': invoice_totals,
            'price_details': price_details(node),
            'has_invoice_amount': bool(invoice_totals), 'has_children': bool(node['children']),
        })
    return {
        'merged': len(roots) > 1,
        'settlement_mode': payment_method(source),
        'client_short_name': source.client_short_name,
        'sub_client_short_name': getattr(source, 'sub_client_short_name', None),
        'items': items,
        'invoice_totals': totals,
    }


@router.put('/project/{project_id}/invoice',dependencies=[Depends(require_any_permission('projects:write','finance:write'))])
def save_invoice(project_id:UUID,payload:InvoiceWrite,order_id:UUID|None=None,db:Session=Depends(get_db),user=Depends(get_current_user),special:bool=False):
    from translation_project_invoices import save
    try:return save(db,project_id,payload,user.id,order_id,special=special)
    except Exception:
        db.rollback();raise


@router.put('/project/{project_id}/invoice/customer-sent', dependencies=[Depends(require_any_permission('projects:write','finance:write'))])
def update_invoice_customer_sent(project_id: UUID, payload: InvoiceCustomerSentWrite, db=Depends(get_db), user=Depends(get_current_user),
                                 order_id:UUID|None=None,special:bool=False):
    from translation_project_invoices import set_customer_sent
    return set_customer_sent(db, project_id, user, payload.sent,order_id=order_id,special=special)
