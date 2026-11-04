"""客户标注单价；只维护客户资料，不自动改写项目报价。"""
from tax_prices import TaxPrices, reference_tax_prices
from tax_prices import TaxPriceMixin, TaxFieldsMixin
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Uuid, DateTime, UniqueConstraint, CheckConstraint
from sqlalchemy.exc import IntegrityError

from annotation_progress_time import business_now, business_datetime
from annotation_schemas import ANNOTATION_PROJECT_TYPE_LABELS
from database import get_db
from models import Base, Client
from routers.auth import require_module_access


class CustomerAnnotationRate(TaxPriceMixin, Base):
    __tablename__ = 'customer_annotation_rate'
    __table_args__ = (
        UniqueConstraint('client_id', 'project_type', 'currency', 'unit', name='uq_customer_annotation_rate_key'),
        CheckConstraint('amount > 0 AND revision >= 1', name='ck_customer_annotation_rate_values'),
    )
    id = Column(Uuid, primary_key=True, default=uuid4)
    client_id = Column(Uuid, ForeignKey('client.id', ondelete='CASCADE'), nullable=False, index=True)
    project_type = Column(String(50), nullable=False)
    amount = Column(Numeric(18, 6), nullable=False)
    currency = Column(String(3), nullable=False, default='CNY')
    unit = Column(String(30), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    updated_by = Column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    updated_at = Column(DateTime(timezone=True), nullable=False)


class RateInput(BaseModel):
    tax_prices: TaxPrices | None = None
    project_type: str
    amount: Decimal = Field(gt=0, le=Decimal('99999999.999999'), max_digits=14, decimal_places=6)
    currency: Literal['CNY', 'USD', 'HKD', 'EUR', 'GBP'] = 'CNY'
    unit: Literal['word', 'thousand_words', 'hour', 'work_hour', 'effective_hour', 'day', 'occurrence', 'item', 'second', 'minute', 'page', 'image', 'project']

    @field_validator('project_type')
    @classmethod
    def validate_type(cls, value):
        if value not in ANNOTATION_PROJECT_TYPE_LABELS:
            raise ValueError('请选择有效的标注类型')
        return value


class RateUpdate(RateInput):
    revision: int = Field(ge=1)


access = require_module_access('clients:read', 'clients:write')
router = APIRouter(prefix='/clients/{client_id}/annotation-rates', tags=['客户标注单价'])


def ensure_client(db, client_id, lock=False):
    query = db.query(Client.id).filter(Client.id == client_id)
    if lock:
        query = query.with_for_update()
    if not query.first():
        raise HTTPException(404, '客户不存在')


def serialize(row):
    return dict(id=str(row.id), project_type=row.project_type, amount=str(row.amount),
                currency=row.currency, unit=row.unit, revision=row.revision,
                updated_at=business_datetime(row.updated_at).isoformat(), tax_prices=row.tax_prices)


@router.get('')
def read_rates(client_id: UUID, db=Depends(get_db), user=Depends(access)):
    ensure_client(db, client_id)
    rows = db.query(CustomerAnnotationRate).filter_by(client_id=client_id).order_by(
        CustomerAnnotationRate.project_type, CustomerAnnotationRate.currency, CustomerAnnotationRate.unit,
    ).all()
    return {'items': [serialize(row) for row in rows]}


def commit_rate(db, row):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, '该标注类型、货币和单位的客户单价已存在，请编辑原单价')
    db.refresh(row)
    return serialize(row)


@router.post('', status_code=201)
def create_rate(client_id: UUID, payload: RateInput, db=Depends(get_db), user=Depends(access)):
    ensure_client(db, client_id, lock=True)
    values=payload.model_dump();values['tax_prices']=reference_tax_prices(values.get('tax_prices'))
    row = CustomerAnnotationRate(client_id=client_id, **values, revision=1,
                                 updated_by=user.id, updated_at=business_now())
    db.add(row)
    return commit_rate(db, row)


def locked_rate(db, client_id, rate_id, revision):
    ensure_client(db, client_id, lock=True)
    row = db.query(CustomerAnnotationRate).filter_by(client_id=client_id, id=rate_id).with_for_update().first()
    if not row:
        raise HTTPException(404, '客户单价不存在')
    if row.revision != revision:
        raise HTTPException(409, '客户单价已被其他人修改，请刷新后重试')
    return row


@router.put('/{rate_id}')
def update_rate(client_id: UUID, rate_id: UUID, payload: RateUpdate, db=Depends(get_db), user=Depends(access)):
    row = locked_rate(db, client_id, rate_id, payload.revision)
    for key, value in payload.model_dump(exclude={'revision'}).items():
        setattr(row, key, reference_tax_prices(value) if key=='tax_prices' else value)
    row.revision += 1
    row.updated_by, row.updated_at = user.id, business_now()
    return commit_rate(db, row)


@router.delete('/{rate_id}', status_code=204)
def delete_rate(client_id: UUID, rate_id: UUID, revision: int = Query(ge=1), db=Depends(get_db), user=Depends(access)):
    row = locked_rate(db, client_id, rate_id, revision)
    db.delete(row)
    db.commit()


class CustomerAnnotationRateTax(TaxFieldsMixin, Base):
    __tablename__ = 'customer_annotation_rate_tax'
    from sqlalchemy import Column as _Column, Uuid as _Uuid, ForeignKey as _ForeignKey
    id = _Column(_Uuid, _ForeignKey('customer_annotation_rate.id', ondelete='CASCADE'), primary_key=True)
