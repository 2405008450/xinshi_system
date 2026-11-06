"""客户字数自动取唯一已填口径，以及我司字数计价。旧收费表保持原结构。"""
from sqlalchemy import Column,ForeignKey,String,Uuid,inspect
from models import Base

LEGACY_METRICS=('characters_no_spaces','words','cjk_chars_korean_words','foreign_words','documents','pages')
METRICS=(*LEGACY_METRICS,'minutes','hours')
def storage_metric(metric):return metric if metric in LEGACY_METRICS else 'words'
MODES={'customer_auto',*(f'company_{metric}' for metric in METRICS)}


class TranslationChargeQuantityBasis(Base):
    __tablename__='translation_charge_quantity_basis'
    charge_id=Column(Uuid,ForeignKey('translation_sub_order_charge_item.id',ondelete='CASCADE'),primary_key=True)
    mode=Column(String(40),nullable=False)


def valid(mode):
    return mode in MODES or mode in METRICS or (str(mode).startswith('customer_auto:') and str(mode).split(':',1)[1] in METRICS)


def resolve(matrix,mode):
    matrix=matrix or {}
    if str(mode).startswith('customer_auto'):
        values=matrix.get('customer',{})
        filled=[(key,values.get(key)) for key in METRICS if values.get(key) is not None]
        selected=str(mode).split(':',1)[1] if ':' in str(mode) else None
        if selected:
            value=values.get(selected)
            return value,'customer',selected,None if value is not None else '未登记对应数量'
        if len(filled)==1:return filled[0][1],'customer',filled[0][0],None
        if not filled:
            own=[(key,matrix.get('company',{}).get(key)) for key in METRICS if matrix.get('company',{}).get(key) is not None]
            if len(own)==1:return own[0][1],'company',own[0][0],None
            if len(own)>1:return None,'company',None,'我司统计有多栏，请选择统计口径'
            return None,'customer',None,'客户统计和我司统计均未填写，请先登记数量和单位'
        return None,'customer',None,'客户字数有多栏，请明确选择统计口径'
    dimension='company' if str(mode).startswith('company_') else 'customer'
    metric=str(mode)[8:] if dimension=='company' else mode
    value=matrix.get(dimension,{}).get(metric)
    return value,dimension,metric,None if value is not None else '未登记对应数量'


def ready(db):
    if 'translation_quantity_basis_ready' not in db.info:db.info['translation_quantity_basis_ready']=inspect(db.connection()).has_table(TranslationChargeQuantityBasis.__tablename__)
    return db.info['translation_quantity_basis_ready']


def metadata(db,ids):
    if not ready(db):return {}
    cache=db.info.setdefault('translation_quantity_basis_cache',{});loaded=db.info.setdefault('translation_quantity_basis_loaded',set())
    missing=set(ids)-loaded
    if missing:cache.update({row.charge_id:row.mode for row in db.query(TranslationChargeQuantityBasis).filter(TranslationChargeQuantityBasis.charge_id.in_(missing)).all()});loaded.update(missing)
    return {key:cache[key] for key in ids if key in cache}


def invalidate(db):
    db.info.pop('translation_quantity_basis_cache',None);db.info.pop('translation_quantity_basis_loaded',None)


def store(db,charge,mode,matrix=None):
    if mode in LEGACY_METRICS:
        charge.metric_type=mode
        if ready(db):
            row=db.get(TranslationChargeQuantityBasis,charge.id)
            if row:db.delete(row)
    else:
        if not ready(db):
            from fastapi import HTTPException
            raise HTTPException(503,'计价口径存储尚未初始化')
        _,_,metric,_=resolve(matrix,mode)
        charge.metric_type=storage_metric(metric) if metric else 'characters_no_spaces'
        row=db.get(TranslationChargeQuantityBasis,charge.id)
        if row is None:row=TranslationChargeQuantityBasis(charge_id=charge.id);db.add(row)
        row.mode=mode
    invalidate(db)
