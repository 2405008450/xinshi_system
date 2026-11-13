"""口译客户财务：组合单价、客户参考价、金额计算及不可覆盖的调整记录。"""
from decimal import Decimal, ROUND_HALF_UP
from tax_prices import reference_tax_prices
from interpretation_finance_schemas import FinanceWrite, InterpretationQuotationWrite, InterpretationSettlement
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, CheckConstraint, inspect, or_, and_, func
from sqlalchemy.exc import IntegrityError
from models import Base, Client
from interpretation_models import InterpretationProject
from database import get_db
from annotation_progress_time import business_now
from routers.auth import get_current_user
from permission_service import user_has_permission
from search_matching import keyword_any, keyword_contains


class InterpretationCustomerFinance(Base):
    __tablename__ = 'interpretation_customer_finance'
    __table_args__ = (UniqueConstraint('project_id'), UniqueConstraint('client_id'),
                      CheckConstraint('(project_id IS NULL) <> (client_id IS NULL)', name='ck_interpretation_finance_owner'),)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(ForeignKey('interpretation_project.id', ondelete='CASCADE'), nullable=True)
    client_id = Column(ForeignKey('client.id', ondelete='CASCADE'), nullable=True)
    revision = Column(Integer, nullable=False, default=0)
    payload = Column(JSON, nullable=False, default=dict)


class InterpretationCustomerFinanceHistory(Base):
    __tablename__ = 'interpretation_customer_finance_history'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    finance_id = Column(ForeignKey('interpretation_customer_finance.id', ondelete='CASCADE'), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    actor_name = Column(String(255), nullable=False)
    actor_id = Column(ForeignKey('app_user.id', ondelete='SET NULL'))
    before = Column(JSON, nullable=False)
    after = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


def calculate(payload):
    totals = {}
    tax_totals = {'excl_tax': {}, 'incl_tax': {}}
    def cents(value):
        return Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

    for row in payload.get('rates', []):
        currency = row['currency']
        totals[currency] = totals.get(currency, Decimal(0)) + cents(Decimal(row['amount']) * Decimal(str(row['quantity'])))
        prices = row.get('tax_prices') or {}
        for kind, values in tax_totals.items():
            value = prices.get('total_' + kind)
            if value is None and prices.get('unit_price_' + kind) is not None:
                value = Decimal(str(prices['unit_price_' + kind])) * Decimal(str(row['quantity']))
            if value is not None:
                values[currency] = values.get(currency, Decimal(0)) + cents(value)
    if payload.get('has_overtime') and payload.get('overtime'):
        row = payload['overtime']
        totals[row['currency']] = totals.get(row['currency'], Decimal(0)) + Decimal(row['amount'])
        for kind, values in tax_totals.items():
            value = (row.get('tax_prices') or {}).get('total_' + kind)
            if value is not None:
                values[row['currency']] = values.get(row['currency'], Decimal(0)) + Decimal(str(value))
    for row in payload.get('adjusted_totals', []):
        for kind,values in tax_totals.items():
            value=(row.get('tax_prices') or {}).get('total_'+kind)
            if value is not None: values[row['currency']]=Decimal(str(value))
    totals = {key: str(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)) for key, value in totals.items()}
    adjusted = {**totals, **{row['currency']: row['amount'] for row in payload.get('adjusted_totals', [])}}
    return dict(totals=totals, adjusted_totals=adjusted,
                totals_excl_tax={key: str(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)) for key, value in tax_totals['excl_tax'].items()},
                totals_incl_tax={key: str(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)) for key, value in tax_totals['incl_tax'].items()})


def settlement(payload):
    return InterpretationSettlement.model_validate(payload.get('settlement') or {})


def billing_totals(payload, amounts):
    return amounts['adjusted_totals' if settlement(payload).tax_basis == 'legacy'
                   else 'totals_' + settlement(payload).tax_basis]


def incomplete_tax_basis(payload, basis):
    adjustments = {row['currency'] for row in payload.get('adjusted_totals', [])
                   if (row.get('tax_prices') or {}).get('total_' + basis) is not None}
    for row in payload.get('rates', []):
        prices = row.get('tax_prices') or {}
        if row['currency'] not in adjustments and all(prices.get(field + basis) is None for field in ('total_', 'unit_price_')):
            return True
    overtime = payload.get('overtime') if payload.get('has_overtime') else None
    return bool(overtime and overtime['currency'] not in adjustments and
                (overtime.get('tax_prices') or {}).get('total_' + basis) is None)


def ready(db):
    inspector = inspect(db.connection())
    return all(inspector.has_table(model.__tablename__) for model in (InterpretationCustomerFinance, InterpretationCustomerFinanceHistory))


def permission(db, user, scope, write=False):
    code = ('projects' if scope == 'project' else 'clients') + (':write' if write else ':read')
    if not user_has_permission(db, user.id, code) and not (not write and user_has_permission(db, user.id, code.replace(':read', ':write'))):
        raise HTTPException(403, '无权操作此财务数据')


def owner(db, scope, target):
    row = db.get(InterpretationProject if scope == 'project' else Client, target)
    if not row:
        raise HTTPException(404, '项目或客户不存在')
    return row


def record(db, scope, target):
    return db.query(InterpretationCustomerFinance).filter_by(**{scope + '_id': target}).populate_existing().first()


def finance_context(scope, entity, available, row, reference=None, *, include_quotation=False):
    from copy import deepcopy
    payload = FinanceWrite(revision=0).model_dump(mode='json', exclude={'revision','update_library','library_revision','sync_confirmed'})
    if row:
        payload.update(deepcopy(row.payload))
    quotation = payload.pop('quotation', None)
    result = dict(ready=available, revision=row.revision if row else 0, payload=payload, **calculate(payload))
    if scope == 'project':
        result.update(id=str(entity.id), order_no=entity.order_no, project_name=entity.project_name,
                      client_short_name=entity.client_short_name or entity.client_full_name,
                      project_status=entity.project_status,
                      directions=[{'id': str(item.id), 'label': ' ↔ '.join(item.language_labels)} for item in entity.language_directions])
        if include_quotation and quotation is not None:
            result['quotation'] = quotation
        if entity.client_id and available:
            result['reference_rates'] = reference.payload.get('rates', []) if reference else []
            result['client_id'] = str(entity.client_id)
            result['library_revision'] = reference.revision if reference else 0
            if not row or 'rates' not in row.payload:
                from customer_finance_sync import oral_defaults
                payload['rates'] = oral_defaults(entity,result['reference_rates'])
                result.update(calculate(payload))
        result['billing_totals'] = billing_totals(payload, result)
    return result


def context(db, scope, target):
    entity = owner(db, scope, target)
    available = ready(db)
    row = record(db, scope, target) if available else None
    reference = record(db, 'client', entity.client_id) if available and scope == 'project' and entity.client_id else None
    return finance_context(scope, entity, available, row, reference, include_quotation=True)


def project_directions(query):
    from sqlalchemy.orm import selectinload
    from interpretation_models import InterpretationProjectLanguageDirection as Direction, InterpretationProjectDirectionExtraLanguage as Extra

    relation = selectinload(InterpretationProject.language_directions)
    return query.options(relation.joinedload(Direction.source_language), relation.joinedload(Direction.target_language),
                         relation.joinedload(Direction.extra_languages).joinedload(Extra.language))


def finance_records(db, projects, available, include_references=False):
    if not available or not projects:
        return {}, {}
    project_ids = [project.id for project in projects]
    client_ids = {project.client_id for project in projects if project.client_id} if include_references else set()
    rows = db.query(InterpretationCustomerFinance).filter(or_(
        InterpretationCustomerFinance.project_id.in_(project_ids),
        InterpretationCustomerFinance.client_id.in_(client_ids),
    )).all()
    return ({row.project_id: row for row in rows if row.project_id},
            {row.client_id: row for row in rows if row.client_id})


def save(db, user, scope, target, data, *, commit=True):
    permission(db, user, scope, True)
    entity = owner(db, scope, target)
    if not ready(db):
        raise HTTPException(503, '口译财务存储尚未初始化')
    # 客户优先加锁；客户下发与项目回写采用同一锁序，避免相互覆盖。
    client_id = entity.client_id if scope == 'project' else target
    if client_id:
        db.query(Client).filter_by(id=client_id).with_for_update().populate_existing().first()
    db.query(InterpretationProject if scope == 'project' else Client).filter_by(id=target).with_for_update().populate_existing().first()
    if scope == 'project':
        directions = {' ↔ '.join(item.language_labels) for item in entity.language_directions}
        if any(rate.direction not in directions for rate in data.rates):
            raise HTTPException(422, '口译方向已变更，请重新打开财务表单')
    payload = data.model_dump(mode='json', exclude={'revision','update_library','library_revision','sync_confirmed','quotation_draft','library_client_id'})
    row = record(db, scope, target)
    before = row.payload if row else {}
    if scope == 'project':
        if data.settlement is None and 'settlement' in before:
            payload['settlement'] = before['settlement']
        if 'quotation' in before:
            payload['quotation'] = before['quotation']
        quotation = getattr(data, 'quotation_draft', None)
        if quotation is not None:
            payload['quotation'] = quotation.model_dump(mode='json')
    if scope == 'client':
        payload.pop('settlement', None)
        for rate in payload['rates']:
            rate['quantity'] = '1'
            rate['tax_prices'] = reference_tax_prices(rate.get('tax_prices'))
        from customer_finance_sync import oral_key
        keys=[oral_key(item) for item in payload['rates']]
        if len(keys)!=len(set(keys)):raise HTTPException(422,'同方向、货币、单位及时长的客户参考价不能重复')
    if row:
        count = db.query(InterpretationCustomerFinance).filter_by(id=row.id, revision=data.revision).update(
            {'revision': data.revision + 1, 'payload': payload}, synchronize_session=False)
        if not count:
            raise HTTPException(409, '财务记录已更新，请重新打开后编辑')
    else:
        if data.revision != 0:
            raise HTTPException(409, '财务版本已变化')
        row = InterpretationCustomerFinance(**{scope + '_id': target}, revision=1, payload=payload)
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, '财务记录已创建，请重新打开后编辑')
    db.add(InterpretationCustomerFinanceHistory(finance_id=row.id, revision=data.revision + 1,
        actor_id=user.id, actor_name=user.full_name or user.username, before=before, after=payload))
    db.flush()
    db.refresh(row)
    from customer_finance_sync import auto_oral, store_oral, oral_key
    if scope == 'client':
        auto_oral(db,user,target,before.get('rates',[]),payload['rates'])
    elif data.update_library:
        permission(db,user,'client',True)
        if not data.sync_confirmed:raise HTTPException(422,'请点击并确认同步客户参考价')
        if not client_id:raise HTTPException(422,'请先为项目选择客户')
        if hasattr(data, 'library_client_id') and data.library_client_id != client_id:
            raise HTTPException(409, '项目客户已变更，请重新确认同步客户单价')
        if not payload['rates']:raise HTTPException(422,'请先登记需要同步的口译单价')
        reference = record(db,'client',client_id)
        if data.library_revision != (reference.revision if reference else 0):raise HTTPException(409,'客户参考价已更新，请重新打开后确认')
        keys=[oral_key(item) for item in payload['rates']]
        if len(set(keys))!=len(keys):raise HTTPException(422,'同方向及单位存在多条单价，请先整理项目价格')
        from copy import deepcopy
        old=deepcopy(reference.payload) if reference else FinanceWrite(revision=0).model_dump(mode='json',exclude={'revision','update_library','library_revision','sync_confirmed'})
        merged={oral_key(item):item for item in old['rates']}
        for item in payload['rates']:
            merged[oral_key(item)]={**item,'quantity':'1','tax_prices':reference_tax_prices(item.get('tax_prices'))}
        if len(merged)>100:raise HTTPException(422,'客户参考价不能超过100条')
        updated={**old,'rates':list(merged.values())}
        store_oral(db,user,'client',client_id,updated,reference)
        auto_oral(db,user,client_id,old['rates'],updated['rates'])
    if commit:
        db.commit()
        db.expire_all()
        return context(db, scope, target)


router = APIRouter(prefix='/interpretation-customer-finance', tags=['interpretation-customer-finance'])


@router.get('/page')
def page(keyword: str = '', client_id: UUID | None = None, only_mine: bool = True, client_manager: str = '', skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100), db=Depends(get_db), user=Depends(get_current_user)):
    # 客户财务页只开放该客户的统计；项目财务页沿用项目权限。
    permission(db, user, 'client' if client_id else 'project')
    from models import SubClient
    query = db.query(InterpretationProject).outerjoin(Client, InterpretationProject.client_id == Client.id).outerjoin(SubClient, InterpretationProject.sub_client_id == SubClient.id)
    if client_id:
        owner(db, 'client', client_id)
        query = query.filter(InterpretationProject.client_id == client_id)
    from project_client_manager import manager_self_expression, manager_name_expression
    fallback = func.coalesce(SubClient.client_manager, Client.client_manager)
    if only_mine:
        query = query.filter(manager_self_expression('interpretation', InterpretationProject.id, user.id, [user.full_name, user.username], fallback))
    elif client_manager.strip():
        query = query.filter(keyword_contains(manager_name_expression('interpretation', InterpretationProject.id, fallback), client_manager.strip()))
    query = query.filter(keyword_any([InterpretationProject.order_no, InterpretationProject.project_name, Client.client_name, Client.client_short_name, SubClient.client_name, SubClient.client_short_name], keyword))
    projects = project_directions(query).order_by(InterpretationProject.created_at.desc(), InterpretationProject.id).all()
    available = ready(db)
    records, references = finance_records(db, projects, available, include_references=True)
    items = [finance_context('project', item, available, records.get(item.id), references.get(item.client_id))
             for item in projects]
    totals, adjusted, excl, incl = {}, {}, {}, {}
    for item in items:
        for field, acc in [('totals', totals), ('adjusted_totals', adjusted),('totals_excl_tax',excl),('totals_incl_tax',incl)]:
            for currency, amount in item[field].items():
                acc[currency] = acc.get(currency, Decimal(0)) + Decimal(amount)
    return dict(items=items[skip:skip+limit], total=len(items), totals={k:str(v) for k,v in totals.items()},
                adjusted_totals={k:str(v) for k,v in adjusted.items()}, totals_excl_tax={k:str(v) for k,v in excl.items()},totals_incl_tax={k:str(v) for k,v in incl.items()}, incomplete=sum(not row['payload']['rates'] for row in items))


@router.get('/{scope}/{target}/history')
def history(scope: Literal['project', 'client'], target: UUID, page: int = Query(1, ge=1), db=Depends(get_db), user=Depends(get_current_user)):
    permission(db, user, scope)
    owner(db, scope, target)
    if not ready(db):
        return dict(items=[], total=0)
    row = record(db, scope, target)
    if not row:
        return dict(items=[], total=0)
    query = db.query(InterpretationCustomerFinanceHistory).filter_by(finance_id=row.id)
    events = query.order_by(InterpretationCustomerFinanceHistory.revision.desc()).offset((page-1)*10).limit(10).all()
    return dict(total=query.count(), items=[dict(id=item.id, revision=item.revision, actor_name=item.actor_name,
        created_at=item.created_at.replace(tzinfo=business_now().tzinfo).isoformat() if item.created_at.tzinfo is None else item.created_at.astimezone(business_now().tzinfo).isoformat(),
        before=item.before, after=item.after) for item in events])


@router.get('/{scope}/{target}')
def get_context(scope: Literal['project', 'client'], target: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    permission(db, user, scope)
    return context(db, scope, target)


@router.put('/{scope}/{target}')
def put_context(scope: Literal['project', 'client'], target: UUID, data: FinanceWrite, db=Depends(get_db), user=Depends(get_current_user)):
    try:
        return save(db, user, scope, target, data)
    except Exception:
        db.rollback()
        raise


def quotation_context(project, row, payload=None):
    from interpretation_finance_schemas import InterpretationQuotation
    saved = (row.payload if row else {}).get('quotation')
    if saved is None:
        payload = payload or {}
        basis = settlement(payload).tax_basis
        items = []
        for rate in payload.get('rates', []):
            price = rate['amount'] if basis == 'legacy' else (rate.get('tax_prices') or {}).get('unit_price_' + basis)
            items.append(dict(description=project.project_name or '口译服务', language_pair=rate['direction'],
                              quantity=rate['quantity'], unit=rate['unit'], unit_price=price, currency=rate['currency']))
        overtime = payload.get('overtime') if payload.get('has_overtime') else None
        if overtime:
            price = overtime['amount'] if basis == 'legacy' else (overtime.get('tax_prices') or {}).get('total_' + basis)
            items.append(dict(description='加班费', quantity=1, unit='项', unit_price=price, currency=overtime['currency']))
        saved = dict(client_name=project.client_full_name or project.client_short_name or '',
                     items=items[:100] or [dict(description=project.project_name or '口译服务')],
                     notes=settlement(payload).customer_explanation)
    document = InterpretationQuotation.model_validate(saved)
    return dict(order_no=project.order_no, revision=row.revision if row else 0, document=document.model_dump(mode='json'))


@router.get('/quotation/project/{target}')
def get_quotation(target: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    permission(db, user, 'project')
    project = owner(db, 'project', target)
    if not ready(db):
        raise HTTPException(503, '口译财务存储尚未初始化')
    return quotation_context(project, record(db, 'project', target), context(db, 'project', target)['payload'])


@router.put('/quotation/project/{target}')
def put_quotation(target: UUID, data: InterpretationQuotationWrite, db=Depends(get_db), user=Depends(get_current_user)):
    permission(db, user, 'project', True)
    if not ready(db):
        raise HTTPException(503, '口译财务存储尚未初始化')
    project = db.query(InterpretationProject).filter_by(id=target).with_for_update().first()
    if project is None:
        raise HTTPException(404, '口译项目不存在')
    row = record(db, 'project', target)
    if data.revision != (row.revision if row else 0):
        raise HTTPException(409, '口译财务数据已变化，请重新打开报价单')
    from customer_finance_sync import store_oral
    row = store_oral(db, user, 'project', target,
                     {**(row.payload if row else {}), 'quotation': data.document.model_dump(mode='json')}, row)
    db.commit()
    return quotation_context(project, row)


@router.get('/statement/project/{target}')
def statement_preview(target: UUID, month: str = Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),
                      scope: Literal['project', 'customer'] = 'project',
                      basis: Literal['legacy', 'excl_tax', 'incl_tax'] | None = None,
                      format: Literal['preview', 'excel', 'pdf'] = 'preview',
                      version: str | None = None, db=Depends(get_db), user=Depends(get_current_user)):
    from fastapi import Response
    from interpretation_statements import build

    permission(db, user, 'project')
    result = build(db, target, month, scope, basis)
    if format == 'preview':
        return result
    if version != result['statement_version']:
        raise HTTPException(409, '对账单数据已变化，请重新生成后下载')
    if not result['rows']:
        raise HTTPException(422, '所选账单月份暂无可生成的项目')
    if format == 'pdf':
        from statement_pdf import pdf_bytes
        return Response(pdf_bytes([result]), media_type='application/pdf')
    from customer_statements import excel_bytes
    return Response(excel_bytes(result), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
