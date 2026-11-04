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
from models import Base, Client
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


def order_rates(db,owner,language_pair=None,meta=None):
    charges=sorted([row for row in owner.customer_charge_items if row.pricing_mode=='metric'],key=lambda row:row.sequence_no or 0)
    meta=metadata(db,[row.id for row in charges]) if meta is None else meta
    bases=quantity_basis.metadata(db,[row.id for row in charges])
    return [{'id':str(row.id),'language_pair':meta[row.id].language_pair if row.id in meta else language_pair or owner.language_pair or '',
             'amount':str(Decimal(str(row.unit_price_excl_tax if row.unit_price_excl_tax is not None else row.unit_price)).normalize()) if row.unit_price_excl_tax is not None or row.unit_price is not None else None,
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


def library(db,client_id):
    if not ready(db):return {'ready':False,'items':[],'version':''}
    client=db.get(Client,client_id)
    if not client:raise HTTPException(404,'客户不存在')
    rows=db.query(CustomerTranslationRate).filter_by(client_id=client_id).order_by(CustomerTranslationRate.rate_key).all()
    digest=[[str(row.id),row.revision,row.active] for row in rows]
    return {'ready':True,'client':{'id':str(client.id),'name':client.client_name,'short_name':client.client_short_name,'code':client.client_code},'items':[serialize(row) for row in rows if row.active],'version':hashlib.sha256(json.dumps(digest).encode()).hexdigest()}


def write_library(db,user,client_id,items,expected,origin='client',merge=False):
    if not ready(db):raise HTTPException(503,'客户语种单价存储尚未初始化')
    if not db.query(Client).filter_by(id=client_id).with_for_update().first():raise HTTPException(404,'客户不存在')
    before=library(db,client_id)
    if expected!=before['version']:raise HTTPException(409,'客户参考价已更新，请刷新后重新确认同步')
    values=[normalize(db,item) for item in items];keys=[rate_key(item) for item in values]
    if len(keys)!=len(set(keys)):raise HTTPException(422,'同语种方向、货币及计价口径的参考价不能重复')
    existing={row.rate_key:row for row in db.query(CustomerTranslationRate).filter_by(client_id=client_id).all()}
    if merge and len({key for key,row in existing.items() if row.active}|set(keys))>100:raise HTTPException(422,'每个客户最多维护100条有效参考价，请先整理客户参考价')
    for data,key in zip(values,keys):
        row=existing.get(key)
        if row is None:
            row=CustomerTranslationRate(id=uuid4(),client_id=client_id,rate_key=key,revision=0);db.add(row)
        row.language_pair=data['language_pair'];row.amount=data['amount'];row.currency=data['currency'];row.metric=data['metric'];row.unit_size=data['unit_size']
        row.tax_prices=reference_tax_prices(data.get('tax_prices'));row.active=True;row.revision+=1;row.updated_by=user.id;row.updated_at=business_now()
    if not merge:
        for key,row in existing.items():
            if key not in keys and row.active:row.active=False;row.revision+=1;row.updated_by=user.id;row.updated_at=business_now()
    db.flush();after=library(db,client_id)
    db.add(CustomerTranslationRateHistory(client_id=client_id,actor_id=user.id,actor_name=user.full_name or user.username,origin=origin,
        before_snapshot=before['items'],after_snapshot=after['items'],created_at=business_now()))
    from customer_finance_sync import auto_translation
    auto_translation(db,user,client_id,before['items'],after['items'])
    return after


router=APIRouter(prefix='/customer-translation-rates',tags=['customer-translation-rates'])


def read_access(db=Depends(get_db),user=Depends(get_current_user)):
    if not any(user_has_permission(db,user.id,code) for code in ('clients:read','clients:write','projects:read','projects:write')):raise HTTPException(403,'无权查看客户参考价')
    return user


@router.get('/{client_id}',dependencies=[Depends(read_access)])
def get(client_id:UUID,db=Depends(get_db)):
    return library(db,client_id)


@router.put('/{client_id}',dependencies=[Depends(require_permission('clients:write'))])
def put(client_id:UUID,payload:LibraryWrite,db=Depends(get_db),user=Depends(get_current_user)):
    try:
        result=write_library(db,user,client_id,payload.items,payload.version);db.commit();return result
    except Exception:db.rollback();raise


@router.get('/{client_id}/history',dependencies=[Depends(read_access)])
def history(client_id:UUID,page:int=Query(1,ge=1),db=Depends(get_db)):
    if not ready(db):return {'items':[],'total':0}
    query=db.query(CustomerTranslationRateHistory).filter_by(client_id=client_id)
    total=query.count();rows=query.order_by(CustomerTranslationRateHistory.created_at.desc(),CustomerTranslationRateHistory.id.desc()).offset((page-1)*10).limit(10).all()
    return {'total':total,'items':[{'id':str(row.id),'actor_name':row.actor_name,'created_at':business_datetime(row.created_at).isoformat(),'origin':row.origin,'before':row.before_snapshot,'after':row.after_snapshot} for row in rows]}


class CustomerTranslationRateTax(TaxFieldsMixin, Base):
    __tablename__ = 'customer_translation_rate_tax'
    from sqlalchemy import Column as _Column, Uuid as _Uuid, ForeignKey as _ForeignKey
    id = _Column(_Uuid, _ForeignKey('customer_translation_rate.id', ondelete='CASCADE'), primary_key=True)
