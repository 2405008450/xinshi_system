from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from tests.test_chat_participant_access import environment
from tax_prices import TaxPrices
from annotation_models import AnnotationProjectPriceItem
from recruitment_models import RecruitmentProject
from customer_annotation_rates import CustomerAnnotationRate
from customer_translation_rates import CustomerTranslationRate
from interpretation_customer_finance import calculate
from tools.apply_project_tax_prices_migration import apply_migration, TABLES


@pytest.mark.parametrize('model,values', [
    (AnnotationProjectPriceItem, dict(project_id=uuid4(), sequence_no=1, amount=1, unit='条')),
    (RecruitmentProject, dict(order_no='RP-TAX')),
    (CustomerAnnotationRate, dict(client_id=uuid4(), project_type='audio_annotation', amount=1, currency='CNY', unit='item', revision=1)),
    (CustomerTranslationRate, dict(client_id=uuid4(), rate_key='key', language_pair='英→中', amount=1, currency='CNY', metric='words', unit_size=1, revision=1, active=True)),
])
def test_tax_prices_roundtrip_independent_legacy_and_clear(environment, model, values):
    db, _ = environment
    row = model(id=uuid4(), **values)
    db.add(row); db.commit()
    assert row.tax_prices is None  # 不能把历史单价 1 认定为某一种税口径。
    row.tax_prices = TaxPrices(unit_price_excl_tax='1.123456', unit_price_incl_tax='1.234567', total_excl_tax='21.12', total_incl_tax='23.45')
    db.commit(); db.expire_all()
    loaded = db.get(model, row.id)
    assert Decimal(loaded.tax_prices['unit_price_excl_tax']) == Decimal('1.123456')
    assert Decimal(loaded.tax_prices['unit_price_incl_tax']) == Decimal('1.234567')
    assert Decimal(loaded.tax_prices['total_excl_tax']) == Decimal('21.12')
    assert Decimal(loaded.tax_prices['total_incl_tax']) == Decimal('23.45')
    loaded.tax_prices = None; db.commit()
    assert loaded.tax_prices['total_incl_tax'] is not None  # 旧客户端缺字段不能清掉数据。
    loaded.tax_prices = {}; db.commit(); db.expire_all()
    assert all(value is None for value in db.get(model, row.id).tax_prices.values())


def test_oral_totals_are_separate_unknown_is_not_zero_tax():
    payload = {'rates': [{'amount': '9', 'quantity': '3', 'currency': 'CNY', 'tax_prices': {
        'unit_price_excl_tax': '10.123456', 'unit_price_incl_tax': '12.654321',
    }}]}
    result = calculate(payload)
    assert result['totals_excl_tax'] == {'CNY': '30.37'}
    assert result['totals_incl_tax'] == {'CNY': '37.96'}
    unknown = calculate({'rates': [{'amount': '100', 'quantity': '3', 'currency': 'CNY'}]})
    assert unknown['totals_excl_tax'] == {} and unknown['totals_incl_tax'] == {}
    payload['rates'][0]['tax_prices']['total_incl_tax'] = '40.01'
    assert calculate(payload)['totals_incl_tax'] == {'CNY': '40.01'}


def test_migration_repeatable_and_no_old_columns_changed(environment):
    db, _ = environment
    from models import Base
    for table in TABLES:
        Base.metadata.tables[table].drop(db.connection())
    before = {table: [column['name'] for column in inspect(db.connection()).get_columns(table)] for table in (
        'annotation_project_price_item', 'recruitment_project', 'customer_annotation_rate', 'customer_translation_rate')}
    apply_migration(db.connection()); apply_migration(db.connection())
    for table, columns in before.items():
        assert [column['name'] for column in inspect(db.connection()).get_columns(table)] == columns
    assert all(inspect(db.connection()).has_table(table) for table in TABLES)
