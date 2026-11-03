from tax_prices import reference_tax_prices
"""从标注项目逐条引入客户单价，保留项目原报价。"""
import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import inspect, or_, select

from annotation_models import AnnotationProject, AnnotationProjectPriceItem
from annotation_progress_time import business_now
from customer_annotation_rates import CustomerAnnotationRate, RateInput, ensure_client
from models import SubClient

UNIT_ALIASES = {'字': 'word', '千字': 'thousand_words', '小时': 'hour', '工作小时': 'work_hour',
                '有效小时': 'effective_hour', '天': 'day', '次': 'occurrence', '条': 'item',
                '秒': 'second', '分钟': 'minute', '页': 'page', '张': 'image', '项目': 'project'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def library(db, client_id):
    rows = db.query(CustomerAnnotationRate).filter_by(client_id=client_id).order_by(CustomerAnnotationRate.id).all()
    values = [dict(id=str(row.id), project_type=row.project_type, amount=str(row.amount), currency=row.currency,
                   unit=row.unit, revision=row.revision, tax_prices=row.tax_prices) for row in rows]
    return rows, digest(values)


def source_query(db, client_id):
    return db.query(AnnotationProjectPriceItem, AnnotationProject).join(
        AnnotationProject, AnnotationProject.id == AnnotationProjectPriceItem.project_id,
    ).filter(or_(AnnotationProject.client_id == client_id, AnnotationProject.sub_client_id.in_(
        select(SubClient.id).where(SubClient.parent_client_id == client_id),
    )))


def source_value(price, project):
    unit = price._normalize_display_unit().strip()
    value = dict(project_type=price.project_type or (project.project_types[0] if len(project.project_types or []) == 1 else ''),
                 amount=str(price.amount), currency=price.currency or 'CNY', unit=UNIT_ALIASES.get(unit, unit), tax_prices=reference_tax_prices(price.tax_prices))
    blocked = ''
    try:
        RateInput(**value)
    except ValidationError:
        blocked = '请先在项目中补全有效的标注类型、货币和计价单位后再引入'
    version = digest(dict(value, id=str(price.id), source_language_id=str(price.source_language_id), target_language_id=str(price.target_language_id)))
    return value, version, blocked


def key(value):
    return value['project_type'], value['currency'], value['unit']


def differences(db, user, client_id, page):
    from customer_finance_sync import require, number
    require(db, user, 'clients:read'); require(db, user, 'projects:read')
    ensure_client(db, client_id)
    if not inspect(db.connection()).has_table(CustomerAnnotationRate.__tablename__):
        return dict(ready=False, items=[], total=0)
    refs, customer_version = library(db, client_id)
    result = []
    for price, project in source_query(db, client_id).order_by(AnnotationProject.order_no.desc(), AnnotationProjectPriceItem.sequence_no).all():
        value, version, blocked = source_value(price, project)
        matching = [dict(project_type=row.project_type, amount=str(row.amount), currency=row.currency, unit=row.unit,tax_prices=row.tax_prices)
                    for row in refs if (row.project_type, row.currency, row.unit) == key(value)]
        if matching and number(matching[0]['amount']) == number(value['amount']) and (matching[0].get('tax_prices') or {}) == (value.get('tax_prices') or {}):
            continue
        result.append(dict(project_id=str(project.id), order_id=str(price.id), order_no=project.order_no,
                           project_name=project.project_name, project_rates=[value], customer_rates=matching,
                           version=version, customer_version=customer_version, sync_blocked_reason=blocked))
    return dict(ready=True, items=result[(page-1)*10:page*10], total=len(result))


def synchronize(db, user, client_id, data):
    from customer_finance_sync import require
    require(db, user, 'clients:write'); require(db, user, 'projects:read')
    if not data.confirmed:
        raise HTTPException(422, '请确认引入项目单价')
    if data.direction != 'project_to_client':
        raise HTTPException(422, '标注项目目前支持将项目单价引入客户资料')
    try:
        ensure_client(db, client_id, lock=True)
        source = source_query(db, client_id).filter(AnnotationProjectPriceItem.id == data.order_id,
                     AnnotationProject.id == data.project_id).with_for_update(of=AnnotationProjectPriceItem).first()
        if not source:
            raise HTTPException(404, '该客户的项目单价不存在')
        value, version, blocked = source_value(*source)
        refs, customer_version = library(db, client_id)
        if version != data.version or customer_version != data.customer_version:
            raise HTTPException(409, '客户或项目单价已变化，请刷新后重新确认')
        if blocked:
            raise HTTPException(422, blocked)
        row = next((row for row in refs if (row.project_type, row.currency, row.unit) == key(value)), None)
        if row is None:
            row = CustomerAnnotationRate(id=uuid4(), client_id=client_id, revision=0)
            db.add(row)
        for field, field_value in RateInput(**value).model_dump().items():
            setattr(row, field, field_value)
        row.revision += 1
        row.updated_at, row.updated_by = business_now(), user.id
        db.commit()
        return dict(success=True)
    except Exception:
        db.rollback()
        raise
