"""业务日期与服务器操作日期分开，客户端不得传入操作身份。"""
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecordWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: UUID
    revision: int = Field(default=0, ge=0)
    work_date: date
    full_name: str = Field(min_length=1, max_length=255)
    wechat: str = Field(default="", max_length=100)
    pull_description: str = Field(default="", max_length=20000)
    moments_description: str = Field(default="", max_length=20000)
    groups_description: str = Field(default="", max_length=20000)
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    remarks: str = Field(default="", max_length=20000)

    @field_validator("amount", mode="before")
    @classmethod
    def reject_bool(cls, value):
        if isinstance(value, bool):
            raise ValueError("金额必须是数字")
        return value


class PaymentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    payment_status: Literal["unpaid", "paid"]
    payment_date: date | None = None

    @model_validator(mode="after")
    def validate_date(self):
        if self.payment_status == "paid" and self.payment_date is None:
            raise ValueError("登记已支付时必须填写付款日期")
        if self.payment_status == "unpaid":
            self.payment_date = None
        return self
