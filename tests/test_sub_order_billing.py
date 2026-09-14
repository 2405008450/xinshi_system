from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

import crud
from schemas import TranslationSubOrderChargeItemInput


def test_metric_charge_calculates_and_preserves_manual_override():
    calculated = SimpleNamespace(
        pricing_mode="metric",
        metric_type="words",
        unit_size=Decimal("1000"),
        unit_price=Decimal("123.4567"),
        amount_override=None,
    )
    overridden = SimpleNamespace(
        pricing_mode="metric",
        metric_type="pages",
        unit_size=Decimal("1"),
        unit_price=Decimal("10"),
        amount_override=Decimal("88.00"),
    )
    fixed = SimpleNamespace(
        pricing_mode="fixed",
        metric_type=None,
        unit_size=None,
        unit_price=None,
        amount_override=Decimal("50.00"),
    )
    sub_order = SimpleNamespace(
        word_count_matrix={"customer": {"words": 1500, "pages": 10}},
        customer_charge_items=[calculated, overridden, fixed],
    )

    crud._attach_customer_charge_amounts([sub_order])

    assert calculated.quantity == 1500
    assert calculated.calculated_amount == Decimal("185.19")
    assert calculated.final_amount == Decimal("185.19")
    assert overridden.calculated_amount == Decimal("100.00")
    assert overridden.final_amount == Decimal("88.00")
    assert fixed.quantity is None
    assert fixed.calculated_amount is None
    assert fixed.final_amount == Decimal("50.00")


def test_charge_schema_supports_currency_and_rejects_incomplete_metric_charge():
    item = TranslationSubOrderChargeItemInput(
        id=uuid4(),
        item_name="排版费",
        pricing_mode="fixed",
        currency=" usd ",
        amount_override="99.90",
    )
    assert item.currency == "USD"
    assert item.amount_override == Decimal("99.90")
    assert item.total_excl_tax == Decimal("99.90")

    words = TranslationSubOrderChargeItemInput(
        item_name="翻译费", pricing_mode="metric", metric_type="words", unit_price=100,
    )
    pages = TranslationSubOrderChargeItemInput(
        item_name="排版费", pricing_mode="metric", metric_type="pages", unit_price=20,
    )
    assert words.unit_size == Decimal("1000")
    assert pages.unit_size == Decimal("1")

    modern = TranslationSubOrderChargeItemInput(
        item_name="翻译费",
        pricing_mode="metric",
        metric_type="words",
        billing_month="2026-09",
        unit_price_excl_tax="100.0000",
        unit_price_incl_tax="106.0000",
        total_excl_tax="150.00",
        total_incl_tax="159.00",
    )
    assert modern.unit_price == Decimal("100.0000")
    assert modern.amount_override == Decimal("150.00")

    with pytest.raises(ValidationError, match="必须选择有效的客户字数口径"):
        TranslationSubOrderChargeItemInput(
            item_name="翻译费",
            pricing_mode="metric",
            unit_size=1000,
            unit_price=100,
        )

    with pytest.raises(ValidationError):
        TranslationSubOrderChargeItemInput(
            item_name="翻译费",
            pricing_mode="fixed",
            billing_month="2026-13",
            total_excl_tax=100,
            total_incl_tax=106,
        )
