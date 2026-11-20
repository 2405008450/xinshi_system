"""客户语种参考价、订单收费语种关联及不可覆盖的变更记录。"""
from tax_prices import TaxPrices, reference_tax_prices
from tax_prices import TaxPriceMixin, TaxFieldsMixin
import hashlib
import json
from decimal import Decimal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Uuid, DateTime, JSON, Boolean, UniqueConstraint, CheckConstraint, inspect
from database import get_db
from models import Base, Client, SubClient
from routers.auth import get_current_user, require_permission
from permission_service import user_has_permission
from annotation_progress_time import business_now,business_datetime
from language_catalog import normalize_language_pairs
import translation_quantity_basis as quantity_basis

METRICS={'characters_no_spaces','words','foreign_words','cjk_chars_korean_words','documents','pages'}


class CustomerTranslationRate(TaxPriceMixin, Base):
    __tablename__='customer_translation_rate'
    __table_args__=(UniqueConstraint('client_id','rate_key',name='uq_customer_translation_rate_key'),CheckConstraint('amount >= 0 AND unit_size > 0 AND revision >= 1',name='ck_customer_translation_rate_values'))
    id=Column(Uuid,primary_key=True,default=uuid4)
    client_id=Column(Uuid,ForeignKey('client.id',ondelete='CASCADE'),nullable=False,index=True)
    rate_key=Column(String(64),nullable=False)
    language_pair=Column(String(255),nullable=False)
    amount=Column(Numeric(14,4),nullable=False)
    currency=Column(String(3),nullable=False)
    metric=Column(String(40),nullable=False)
    unit_size=Column(Numeric(14,4),nullable=False)
    revision=Column(Integer,nullable=False,default=1)
    active=Column(Boolean,nullable=False,default=True)
    updated_by=Column(Uuid,nullable=False)
    updated_at=Column(DateTime(timezone=True),nullable=False)


class TranslationChargeDirection(Base):
    __tablename__='translation_charge_direction'
    charge_id=Column(Uuid,ForeignKey('translation_sub_order_charge_item.id',ondelete='CASCADE'),primary_key=True)
    language_pair=Column(String(255),nullable=False)
    reference_id=Column(Uuid,ForeignKey('customer_translation_rate.id',ondelete='SET NULL'),nullable=True)
    reference_revision=Column(Integer,nullable=True)


class CustomerTranslationRateHistory(Base):
    __tablename__='customer_translation_rate_history'
    id=Column(Uuid,primary_key=True,default=uuid4)
    client_id=Column(Uuid,ForeignKey('client.id',ondelete='CASCADE'),nullable=False,index=True)
    actor_id=Column(Uuid,nullable=False)
    actor_name=Column(String(255),nullable=False)
    origin=Column(String(40),nullable=False)
    before_snapshot=Column(JSON,nullable=False)
    after_snapshot=Column(JSON,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False)


class SubClientTranslationRate(Base):
    __tablename__ = 'sub_client_translation_rate'
    rate_id = Column(Uuid, ForeignKey('customer_translation_rate.id', ondelete='CASCADE'), primary_key=True)
    sub_client_id = Column(Uuid, ForeignKey('sub_client.id', ondelete='CASCADE'), nullable=False, index=True)


def sub_rates_ready(db):
    if 'sub_translation_rates_ready' not in db.info:
        db.info['sub_translation_rates_ready'] = inspect(db.connection()).has_table(SubClientTranslationRate.__tablename__)
    return db.info['sub_translation_rates_ready']


def sub_owner(db, client_id, sub_client_id):
    row = db.get(SubClient, sub_client_id)
    if not row or row.parent_client_id != client_id:
        raise HTTPException(404, '子客户不属于该客户')
    return row


def scoped_rates(db, client_id, sub_client_id=None):
    query = db.query(CustomerTranslationRate).filter_by(client_id=client_id)
    if not sub_rates_ready(db):
        return query.filter(False) if sub_client_id else query.filter(~CustomerTranslationRate.rate_key.startswith('sub:'))
    scope = SubClientTranslationRate
    query = query.outerjoin(scope, scope.rate_id == CustomerTranslationRate.id)
    return query.filter(scope.sub_client_id == sub_client_id) if sub_client_id else query.filter(
        scope.rate_id.is_(None), ~CustomerTranslationRate.rate_key.startswith('sub:'))


def project_rate_defaults(parent, child):
    def key(row):
        # 历史显式指标和选择同一客户统计指标的价格应视为同一计价口径。
        return rate_key(dict(row, metric=row['metric'].removeprefix('customer_auto:')))

    child_keys = {key(row) for row in child}
    return [*child, *(row for row in parent if key(row) not in child_keys)]


def scoped_origin(sub_client_id):
    return f'sub:{sub_client_id}'


def ready(db):
    if 'customer_translation_rates_ready' in db.info:return db.info['customer_translation_rates_ready']
    inspector=inspect(db.connection())
    result=all(inspector.has_table(model.__tablename__) for model in (CustomerTranslationRate,TranslationChargeDirection,CustomerTranslationRateHistory))
    db.info['customer_translation_rates_ready']=result
    return result


def metadata(db,ids):
    if not ready(db):return {}
    cache=db.info.setdefault('translation_charge_direction_cache',{})
    loaded=db.info.setdefault('translation_charge_direction_loaded',set())
    missing=set(ids)-loaded
    if missing:
        cache.update({row.charge_id:row for row in db.query(TranslationChargeDirection).filter(TranslationChargeDirection.charge_id.in_(missing)).all()});loaded.update(missing)
    return {key:cache[key] for key in ids if key in cache}


def invalidate_metadata(db):
    db.info.pop('translation_charge_direction_cache',None);db.info.pop('translation_charge_direction_loaded',None)


def order_unit_amount(charge):
    for amount in (charge.unit_price_excl_tax, charge.unit_price_incl_tax, charge.unit_price):
        if amount is not None:
            return Decimal(str(amount)).normalize()
    return None


def order_rates(db,owner,language_pair=None,meta=None):
    charges=sorted([row for row in owner.customer_charge_items if row.pricing_mode=='metric' and row.item_name!='财务信息'],key=lambda row:row.sequence_no or 0)
    meta=metadata(db,[row.id for row in charges]) if meta is None else meta
    bases=quantity_basis.metadata(db,[row.id for row in charges])
    return [{'id':str(row.id),'language_pair':meta[row.id].language_pair if row.id in meta else language_pair or owner.language_pair or '',
             'amount':str(amount) if (amount:=order_unit_amount(row)) is not None else None,
             'currency':row.currency or 'CNY','metric':bases.get(row.id,row.metric_type),'unit_size':str(Decimal(str(row.unit_size or 1)).normalize()),
             'reference_id':str(meta[row.id].reference_id) if row.id in meta and meta[row.id].reference_id else None,
             'reference_revision':meta[row.id].reference_revision if row.id in meta else None, 'tax_prices':{key:str(getattr(row,key)) if getattr(row,key) is not None else None for key in TaxPrices.model_fields}} for row in charges]


def chinese(label):
    value=str(label).replace(' ','').lower()
    return value in {'中','简中','繁中'} or value.startswith('zh') or any(word in value for word in ('中文','汉语','簡中','繁體','简体','繁体'))


def default_metric(direction):
    return 'customer_auto'


def direction(db,value):
    try:
        value=normalize_language_pairs(value)
        if not value or '；' in value:raise ValueError('每条单价请选择一个语种方向，可新增多条单价')
        import crud
        return crud._normalize_catalog_language_pairs(db,value)
    except ValueError as e:raise HTTPException(422,str(e))


class RateInput(BaseModel):
    tax_prices: TaxPrices | None = None
    model_config=ConfigDict(extra='forbid')
    id:UUID|None=None
    language_pair:str=Field(min_length=1,max_length=255)
    amount:Decimal=Field(ge=0,max_digits=14,decimal_places=4)
    currency:str=Field(default='CNY',pattern=r'^[A-Z]{3}$')
    metric:str|None=None
    unit_size:Decimal=Field(default=Decimal(1),gt=0,max_digits=14,decimal_places=4)
    reference_id:UUID|None=None
    reference_revision:int|None=None


class LibraryWrite(BaseModel):
    version:str
    items:list[RateInput]=Field(max_length=100)


def normalize(db,item):
    data=item.model_dump();data['language_pair']=direction(db,item.language_pair);data['metric']=item.metric or default_metric(data['language_pair'])
    if not quantity_basis.valid(data['metric']):raise HTTPException(422,'请选择有效的计价单位')
    return data


def rate_key(data):
    value=[data['language_pair'].casefold(),data['currency'],data['metric'],str(Decimal(str(data['unit_size'])).normalize())]
    return hashlib.sha256(json.dumps(value,ensure_ascii=False).encode()).hexdigest()


def serialize(row):
    return {'id':str(row.id),'language_pair':row.language_pair,'amount':str(row.amount),'currency':row.currency,'metric':row.metric,
            'unit_size':str(row.unit_size),'revision':row.revision,'active':row.active,'updated_at':business_datetime(row.updated_at).isoformat(),'tax_prices':row.tax_prices}


def library(db,client_id,sub_client_id=None):
    if not ready(db) or sub_client_id and not sub_rates_ready(db):return {'ready':False,'items':[],'version':''}
    client=db.get(Client,client_id)
    if not client:raise HTTPException(404,'客户不存在')
    owner = sub_owner(db, client_id, sub_client_id) if sub_client_id else client
    rows=scoped_rates(db,client_id,sub_client_id).order_by(CustomerTranslationRate.rate_key).all()
    digest=[[str(row.id),row.revision,row.active] for row in rows]
    return {'ready':True,'client':{'id':str(owner.id),'name':owner.client_name,'short_name':owner.client_short_name,'code':owner.sub_client_code if sub_client_id else owner.client_code},'items':[serialize(row) for row in rows if row.active],'version':hashlib.sha256(json.dumps(digest).encode()).hexdigest()}


def record_order_finance(db, user, client_id, order_id, order_no, origin, before, after, *, matches_customer=False, initial=False):
    if not client_id or before == after or not ready(db):
        return
    query = db.query(CustomerTranslationRateHistory).filter_by(client_id=client_id, origin=origin)
    previous = query.filter(CustomerTranslationRateHistory.after_snapshot['order_id'].as_string()==str(order_id)).order_by(
        CustomerTranslationRateHistory.created_at.desc(), CustomerTranslationRateHistory.id.desc()).first()
    if (matches_customer and not previous) or (initial and previous and previous.after_snapshot['values']==after):
        return
    revision = previous.after_snapshot['revision'] + 1 if previous else 1
    db.add(CustomerTranslationRateHistory(
        client_id=client_id, actor_id=user.id, actor_name=user.full_name or user.username,
        origin=origin, before_snapshot=before,
        after_snapshot={'order_id':str(order_id),'order_no':order_no,'revision':revision,'values':after},
        created_at=business_now(),
    ))


def history_entry(row):
    after = row.after_snapshot
    details = after if isinstance(after, dict) and 'values' in after else {}
    return {'id':str(row.id), 'actor_name':row.actor_name, 'created_at':business_datetime(row.created_at).isoformat(),
            'origin':row.origin, 'before':row.before_snapshot, 'after':details.get('values', after),
            **{key:value for key,value in details.items() if key != 'values'}}


def record_library_history(db, user, client_id, sub_client_id, before, after, action, *,
                           project_id=None, order_id=None, order_no=None):
    snapshot = {'values': after, 'action': action}
    if project_id is not None:
        snapshot.update(project_id=str(project_id), order_id=str(order_id), order_no=order_no)
    db.add(CustomerTranslationRateHistory(
        client_id=client_id, actor_id=user.id, actor_name=user.full_name or user.username,
        origin=scoped_origin(sub_client_id) if sub_client_id else ('project' if project_id else 'client'),
        before_snapshot=before, after_snapshot=snapshot, created_at=business_now(),
    ))


def write_library(db,user,client_id,items,expected,origin='client',merge=False,*,sub_client_id=None,
                  project_id=None,order_id=None,order_no=None):
    if not ready(db) or sub_client_id and not sub_rates_ready(db):raise HTTPException(503,'客户语种单价存储尚未初始化')
    if not db.query(Client).filter_by(id=client_id).with_for_update().first():raise HTTPException(404,'客户不存在')
    before=library(db,client_id,sub_client_id)
    if expected!=before['version']:raise HTTPException(409,'客户参考价已更新，请刷新后重新确认同步')
    values=[normalize(db,item) for item in items];keys=[rate_key(item) for item in values]
    if len(keys)!=len(set(keys)):raise HTTPException(422,'同语种方向、货币及计价口径的参考价不能重复')
    if sub_client_id:
        keys = ['sub:' + hashlib.sha256(f'{sub_client_id}:{key}'.encode()).hexdigest()[:60] for key in keys]
    existing={row.rate_key:row for row in scoped_rates(db,client_id,sub_client_id).all()}
    if merge and len({key for key,row in existing.items() if row.active}|set(keys))>100:raise HTTPException(422,'每个客户最多维护100条有效参考价，请先整理客户参考价')
    new_scopes = []
    for data,key in zip(values,keys):
        row=existing.get(key)
        if row is None:
            row=CustomerTranslationRate(id=uuid4(),client_id=client_id,rate_key=key,revision=0);db.add(row)
            if sub_client_id:
                new_scopes.append(SubClientTranslationRate(rate_id=row.id, sub_client_id=sub_client_id))
        row.language_pair=data['language_pair'];row.amount=data['amount'];row.currency=data['currency'];row.metric=data['metric'];row.unit_size=data['unit_size']
        row.tax_prices=reference_tax_prices(data.get('tax_prices'));row.active=True;row.revision+=1;row.updated_by=user.id;row.updated_at=business_now()
    if not merge:
        for key,row in existing.items():
            if key not in keys and row.active:row.active=False;row.revision+=1;row.updated_by=user.id;row.updated_at=business_now()
    db.flush()
    db.add_all(new_scopes)
    db.flush()
    after=library(db,client_id,sub_client_id)
    record_library_history(db,user,client_id,sub_client_id,before['items'],after['items'],
                           'automatic_project_sync' if origin=='automatic_project' else 'manual_project_sync' if origin=='project' else 'manual_entry',
                           project_id=project_id,order_id=order_id,order_no=order_no)
    from customer_finance_sync import auto_translation
    auto_translation(db,user,client_id,before['items'],after['items'],changed_only=True,sub_client_id=sub_client_id,overwrite=True)
    return after


router=APIRouter(prefix='/customer-translation-rates',tags=['customer-translation-rates'])


def read_access(db=Depends(get_db),user=Depends(get_current_user)):
    if not any(user_has_permission(db,user.id,code) for code in ('clients:read','clients:write','projects:read','projects:write')):raise HTTPException(403,'无权查看客户参考价')
    return user


@router.get('/{client_id}',dependencies=[Depends(read_access)])
def get(client_id:UUID,db=Depends(get_db),sub_client_id:UUID|None=None):
    return library(db,client_id,sub_client_id)


@router.put('/{client_id}',dependencies=[Depends(require_permission('clients:write'))])
def put(client_id:UUID,payload:LibraryWrite,db=Depends(get_db),user=Depends(get_current_user),sub_client_id:UUID|None=None):
    try:
        result=write_library(db,user,client_id,payload.items,payload.version,sub_client_id=sub_client_id);db.commit();return result
    except Exception:db.rollback();raise


@router.get('/{client_id}/history',dependencies=[Depends(read_access)])
def history(client_id:UUID,page:int=Query(1,ge=1),db=Depends(get_db),sub_client_id:UUID|None=None):
    if not ready(db):return {'items':[],'total':0}
    query=db.query(CustomerTranslationRateHistory).filter_by(client_id=client_id).filter(
        ~CustomerTranslationRateHistory.origin.in_(('document_defaults_client','document_defaults_project','order_documents')))
    if sub_client_id:
        sub_owner(db,client_id,sub_client_id)
        query = query.filter_by(origin=scoped_origin(sub_client_id))
    else:
        query = query.filter(~CustomerTranslationRateHistory.origin.startswith('sub:'))
    total=query.count();rows=query.order_by(CustomerTranslationRateHistory.created_at.desc(),CustomerTranslationRateHistory.id.desc()).offset((page-1)*10).limit(10).all()
    return {'total':total,'items':[history_entry(row) for row in rows]}


class CustomerTranslationRateTax(TaxFieldsMixin, Base):
    __tablename__ = 'customer_translation_rate_tax'
    from sqlalchemy import Column as _Column, Uuid as _Uuid, ForeignKey as _ForeignKey
    id = _Column(_Uuid, _ForeignKey('customer_translation_rate.id', ondelete='CASCADE'), primary_key=True)
