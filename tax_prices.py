"""价格税口径。历史未说明的原金额不自动归类，含税/不含税独立保存。"""
from decimal import Decimal
from pydantic import BaseModel, Field
from sqlalchemy import Column, Numeric
from sqlalchemy.orm import declared_attr, relationship


class TaxPrices(BaseModel):
    unit_price_excl_tax: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6)
    unit_price_incl_tax: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6)
    total_excl_tax: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    total_incl_tax: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)


def reference_tax_prices(value):
    if value is None:
        return None
    data = (value if isinstance(value, TaxPrices) else TaxPrices(**value)).model_dump(mode='json')
    data['total_excl_tax'] = data['total_incl_tax'] = None
    return data


class TaxFieldsMixin:
    unit_price_excl_tax = Column(Numeric(18, 6))
    unit_price_incl_tax = Column(Numeric(18, 6))
    total_excl_tax = Column(Numeric(18, 2))
    total_incl_tax = Column(Numeric(18, 2))


class TaxPriceMixin:
    @declared_attr
    def tax_record(cls):
        return relationship(cls.__name__ + 'Tax', uselist=False, cascade='all, delete-orphan', lazy='selectin')

    @property
    def tax_prices(self):
        if self.tax_record is None:
            return None
        return {key: str(getattr(self.tax_record, key)) if getattr(self.tax_record, key) is not None else None
                for key in TaxPrices.model_fields}

    @tax_prices.setter
    def tax_prices(self, value):
        # 旧客户端没有税口径字段时不清除已经填写的值；清空请显式提交四项空值。
        if value is None:
            return
        payload = value if isinstance(value, TaxPrices) else TaxPrices(**value)
        if self.tax_record is None:
            model = self.__mapper__.relationships['tax_record'].mapper.class_
            self.tax_record = model()
        for key, amount in payload.model_dump().items():
            setattr(self.tax_record, key, amount)
