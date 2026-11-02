"""口译客户财务：组合单价、客户参考价、金额计算及不可覆盖的调整记录。"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
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


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Rate(StrictInput):
    direction: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    currency: str = Field(default='CNY', pattern='^[A-Z]{3}$')
    unit: Literal['月', '周', '天', '半天', '小时'] = '天'
    quantity: Decimal = Field(default=1, ge=0, max_digits=10, decimal_places=4)
    hours: Decimal | None = Field(default=None, gt=0, le=744, max_digits=8, decimal_places=4)
    includes_lunch: bool = False

    @model_validator(mode='after')
    def defaults(self):
        self.direction = self.direction.strip()
        if not self.direction:
            raise ValueError('请填写口译方向')
        if self.unit in ('天', '半天'):
            self.hours = self.hours or Decimal(8 if self.unit == '天' else 3)
        else:
            self.hours = None
        if self.unit != '天':
            self.includes_lunch = False
        return self


class Money(StrictInput):
    amount: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    currency: str = Field(default='CNY', pattern='^[A-Z]{3}$')


class FinanceWrite(StrictInput):
    revision: int = Field(ge=0)
    rates: list[Rate] = Field(default_factory=list, max_length=100)
    has_overtime: bool = False
    overtime: Money | None = None
    adjusted_totals: list[Money] = Field(default_factory=list, max_length=20)
    explanation: str = Field(default='', max_length=5000)
    update_library: bool = False
    library_revision: int | None = Field(default=None, ge=0)
    sync_confirmed: bool = False

    @model_validator(mode='after')
    def validate_totals(self):
        if self.has_overtime and self.overtime is None:
            raise ValueError('有加班费时请填写总加班费')
        if not self.has_overtime:
            self.overtime = None
        currencies = [row.currency for row in self.adjusted_totals]
        if len(set(currencies)) != len(currencies):
            raise ValueError('每种货币只能填写一个调整后总价')
        return self


def calculate(payload):
    totals = {}
    for row in payload.get('rates', []):
        currency = row['currency']
        totals[currency] = totals.get(currency, Decimal(0)) + Decimal(row['amount']) * Decimal(str(row['quantity']))
    if payload.get('has_overtime') and payload.get('overtime'):
        row = payload['overtime']
        totals[row['currency']] = totals.get(row['currency'], Decimal(0)) + Decimal(row['amount'])
    totals = {key: str(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)) for key, value in totals.items()}
    adjusted = {**totals, **{row['currency']: row['amount'] for row in payload.get('adjusted_totals', [])}}
    return dict(totals=totals, adjusted_totals=adjusted)


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


def context(db, scope, target):
    entity = owner(db, scope, target)
    available = ready(db)
    row = record(db, scope, target) if available else None
    from copy import deepcopy
    payload = deepcopy(row.payload) if row else FinanceWrite(revision=0).model_dump(mode='json', exclude={'revision','update_library','library_revision','sync_confirmed'})
    result = dict(ready=available, revision=row.revision if row else 0, payload=payload, **calculate(payload))
    if scope == 'project':
        result.update(id=str(entity.id), order_no=entity.order_no, project_name=entity.project_name,
                      client_short_name=entity.client_short_name or entity.client_full_name,
                      project_status=entity.project_status,
                      directions=[{'id': str(item.id), 'label': ' ↔ '.join(item.language_labels)} for item in entity.language_directions])
        if entity.client_id and available:
            reference = record(db, 'client', entity.client_id)
            result['reference_rates'] = reference.payload.get('rates', []) if reference else []
            result['client_id'] = str(entity.client_id)
            result['library_revision'] = reference.revision if reference else 0
            if not payload['rates']:
                from customer_finance_sync import oral_defaults
                payload['rates'] = oral_defaults(entity,result['reference_rates'])
                result.update(calculate(payload))
    return result


def save(db, user, scope, target, data):
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
    payload = data.model_dump(mode='json', exclude={'revision','update_library','library_revision','sync_confirmed'})
    if scope == 'client':
        from customer_finance_sync import oral_key
        keys=[oral_key(item) for item in payload['rates']]
        if len(keys)!=len(set(keys)):raise HTTPException(422,'同方向、货币、单位及时长的客户参考价不能重复')
    row = record(db, scope, target)
    before = row.payload if row else {}
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
        reference = record(db,'client',client_id)
        if data.library_revision != (reference.revision if reference else 0):raise HTTPException(409,'客户参考价已更新，请重新打开后确认')
        keys=[oral_key(item) for item in payload['rates']]
        if len(set(keys))!=len(keys):raise HTTPException(422,'同方向及单位存在多条单价，请先整理项目价格')
        from copy import deepcopy
        old=deepcopy(reference.payload) if reference else FinanceWrite(revision=0).model_dump(mode='json',exclude={'revision','update_library','library_revision','sync_confirmed'})
        merged={oral_key(item):item for item in old['rates']}
        for item in payload['rates']:merged[oral_key(item)]={**item,'quantity':'1'}
        if len(merged)>100:raise HTTPException(422,'客户参考价不能超过100条')
        updated={**old,'rates':list(merged.values())}
        store_oral(db,user,'client',client_id,updated,reference)
        auto_oral(db,user,client_id,old['rates'],updated['rates'])
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
    projects = query.order_by(InterpretationProject.created_at.desc(), InterpretationProject.id).all()
    items = [context(db, 'project', item.id) for item in projects]
    totals, adjusted = {}, {}
    for item in items:
        for field, acc in [('totals', totals), ('adjusted_totals', adjusted)]:
            for currency, amount in item[field].items():
                acc[currency] = acc.get(currency, Decimal(0)) + Decimal(amount)
    return dict(items=items[skip:skip+limit], total=len(items), totals={k:str(v) for k,v in totals.items()},
                adjusted_totals={k:str(v) for k,v in adjusted.items()}, incomplete=sum(not row['payload']['rates'] for row in items))


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
