"""口译收费在项目表单与财务表单之间共用的字段。"""
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tax_prices import TaxPrices
from translation_document_requirements import PaymentMethod, QuotationDraft, QuotationLine


class InterpretationSettlement(BaseModel):
    model_config = ConfigDict(extra='forbid')

    billing_month: str | None = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    tax_basis: Literal['excl_tax', 'incl_tax', 'legacy'] = 'legacy'
    payment_method: PaymentMethod = 'individual'
    payment_status: Literal['unrecorded', 'deposit', 'partial', 'full'] = 'unrecorded'
    payments: list['InterpretationReceipt'] = Field(default_factory=list, max_length=100)
    quotation_required: bool = False
    invoice_required: bool = False
    customer_explanation: str = Field(default='', max_length=5000)
    payment_note: str = Field(default='', max_length=5000)


class InterpretationReceipt(BaseModel):
    model_config = ConfigDict(extra='forbid')

    amount: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    currency: str = Field(default='CNY', pattern=r'^[A-Z]{3}$')
    received_on: date | None = None
    note: str = Field(default='', max_length=2000)


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Rate(StrictInput):
    tax_prices: TaxPrices | None = None
    direction: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
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
    tax_prices: TaxPrices | None = None


class FinanceWrite(StrictInput):
    revision: int = Field(ge=0)
    rates: list[Rate] = Field(default_factory=list, max_length=100)
    has_overtime: bool = False
    overtime: Money | None = None
    adjusted_totals: list[Money] = Field(default_factory=list, max_length=20)
    explanation: str = Field(default='', max_length=5000)
    settlement: InterpretationSettlement | None = None
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


class InterpretationQuotationLine(QuotationLine):
    unit: Literal['月', '周', '天', '半天', '小时', '项'] = '天'
    currency: str = Field(default='CNY', pattern=r'^[A-Z]{3}$')
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6)


class InterpretationQuotation(QuotationDraft):
    title: str = Field(default='口译服务报价单', min_length=1, max_length=255)
    items: list[InterpretationQuotationLine] = Field(min_length=1, max_length=100)


class InterpretationQuotationWrite(StrictInput):
    revision: int = Field(ge=0)
    document: InterpretationQuotation


class InterpretationProjectFinanceDraft(FinanceWrite):
    quotation_draft: InterpretationQuotation | None = None
    library_client_id: UUID | None = None
