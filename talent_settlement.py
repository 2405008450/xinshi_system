"""人才商务与结算资料、可重复价格明细，沿用人才联系方式的查看权限。"""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import mapped_column

from business_time import BUSINESS_TIMEZONE
from models import Base


class TalentSettlementPrice(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    category: Literal['interpretation', 'written_translation', 'annotation', 'collection'] | None = None
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)
    amount_max: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    currency: Literal['CNY', 'USD', 'HKD', 'EUR', 'GBP', 'BRL', 'IDR'] | None = None
    status: Literal['pending', 'confirmed'] = 'confirmed'
    price_type: Literal['fixed', 'range', 'negotiable'] = 'fixed'
    service_type: Literal['translation', 'proofreading', 'editing', 'lqa'] | None = None
    language_pair: str | None = Field(default=None, max_length=500)
    raw_text: str | None = Field(default=None, max_length=20000)
    source_file: str | None = Field(default=None, max_length=255)
    source_sheet: str | None = Field(default=None, max_length=255)
    source_row: int | None = Field(default=None, ge=1)
    source_column: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode='before')
    @classmethod
    def legacy_currency(cls, value):
        # 旧记录省略币种时沿用旧版人民币语义；新待核报价绝不推断币种。
        if isinstance(value, dict) and 'status' not in value and 'currency' not in value:
            return {**value, 'currency': 'CNY'}
        return value

    @field_validator('category', 'currency', 'service_type', 'unit', 'language_pair', 'raw_text', 'source_file', 'source_sheet', 'source_column', 'notes', mode='before')
    @classmethod
    def clean_text(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @model_validator(mode='after')
    def validate_quote(self):
        if self.amount_max is not None:
            if self.price_type != 'range':
                raise ValueError('仅区间报价可填写金额上限')
            if self.amount is None or self.amount_max < self.amount:
                raise ValueError('金额上限不得小于下限，且必须填写下限')
        if self.status == 'confirmed':
            if self.category is None or self.unit is None or self.currency is None:
                raise ValueError('已确认报价必须填写价格类型、计价单位和币种')
            if self.price_type != 'negotiable' and self.amount is None:
                raise ValueError('已确认报价必须填写金额')
            if self.price_type == 'range' and self.amount_max is None:
                raise ValueError('已确认区间报价必须填写金额上限')
        elif self.amount is None and self.raw_text is None:
            raise ValueError('待核对报价至少填写金额或原始报价')
        return self


class TalentSettlementInput(BaseModel):
    revision: int = Field(default=0, ge=0)
    bank_account: str | None = Field(default=None, max_length=255)
    paypal_account: str | None = Field(default=None, max_length=255)
    payoneer_account: str | None = Field(default=None, max_length=255)
    wechat_payment_code: str | None = Field(default=None, max_length=4000)
    alipay_payment_code: str | None = Field(default=None, max_length=4000)
    invoice_available: bool | None = None
    invoice_entity: str | None = Field(default=None, max_length=255)
    gig_platform_calculation: bool = False
    prices: list[TalentSettlementPrice] = Field(default_factory=list, max_length=100)

    @field_validator('bank_account', 'paypal_account', 'payoneer_account', 'wechat_payment_code', 'alipay_payment_code', 'invoice_entity', mode='before')
    @classmethod
    def clean_text(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @model_validator(mode='after')
    def unique_rows(self):
        if self.invoice_available is True and not self.invoice_entity:
            raise ValueError('可开票时请填写开票主体/名义')
        if self.invoice_available is not True:
            self.invoice_entity = None
        if len({row.id for row in self.prices}) != len(self.prices):
            raise ValueError('价格明细不能包含重复行')
        return self


class TalentSettlementResponse(TalentSettlementInput):
    model_config = ConfigDict(from_attributes=True)


class TalentSettlement(Base):
    __tablename__ = 'talent_settlement'
    __table_args__ = (
        CheckConstraint('revision >= 1',name='ck_talent_settlement_revision'),
        CheckConstraint('invoice_available IS NOT TRUE OR (invoice_entity IS NOT NULL AND length(trim(invoice_entity)) > 0)',name='ck_talent_settlement_invoice_entity'),
    )
    person_id = mapped_column(Uuid, ForeignKey('resource_person.id', ondelete='CASCADE'), primary_key=True)
    revision = mapped_column(Integer, nullable=False, default=1)
    bank_account = mapped_column(String(255))
    paypal_account = mapped_column(String(255))
    payoneer_account = mapped_column(String(255))
    wechat_payment_code = mapped_column(Text)
    alipay_payment_code = mapped_column(Text)
    invoice_available = mapped_column(Boolean)
    invoice_entity = mapped_column(String(255))
    gig_platform_calculation = mapped_column(Boolean, nullable=False, default=False)
    prices = mapped_column(JSON, nullable=False, default=list)
    updated_by = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False)


def read_settlement(db, person_id, *, visible):
    if not visible:
        return None
    row = db.get(TalentSettlement, person_id)
    return TalentSettlementResponse.model_validate(row).model_dump() if row else None


def save_settlement(db, person, payload, actor):
    if 'settlement' not in payload.model_fields_set or payload.settlement is None:
        return
    from talent_privacy import can_view_talent_contacts
    if actor is None or not can_view_talent_contacts(db, actor):
        raise HTTPException(403, '商务与结算资料沿用人才联系方式的访问权限')
    values = payload.settlement.model_dump(mode='json', exclude={'revision'})
    row = db.query(TalentSettlement).filter(TalentSettlement.person_id == person.id).with_for_update().first()
    if row is None:
        meaningful = values['gig_platform_calculation'] or any(value is not None and value != '' and value != []
                         for key, value in values.items() if key != 'gig_platform_calculation')
        if not meaningful:
            return
        if payload.settlement.revision != 0:
            raise HTTPException(409, '结算资料已变化，请重新打开后核对')
        row = TalentSettlement(person_id=person.id, revision=1)
        db.add(row)
    else:
        if payload.settlement.revision != row.revision:
            raise HTTPException(409, '结算资料已被修改，请重新打开后核对；当前输入已保留')
        # 旧版价格缺少新字段时按兼容默认值比较，查看后原样保存不制造版本变更。
        current_values = TalentSettlementResponse.model_validate(row).model_dump(mode='json', exclude={'revision'})
        if current_values == values:
            person.__dict__['settlement'] = TalentSettlementResponse.model_validate(row)
            return
        row.revision += 1
    for key, value in values.items():
        setattr(row, key, value)
    row.updated_by = actor.id
    row.updated_at = datetime.now(BUSINESS_TIMEZONE)
    person.__dict__['settlement'] = TalentSettlementResponse.model_validate(row)
