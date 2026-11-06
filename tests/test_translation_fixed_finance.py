from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event
from tests.test_chat_participant_access import environment
from tests.test_customer_finance_sync import allowed
from tests.test_customer_translation_rates import context, item, write
from models import TranslationSubOrderChargeItem
from schemas import TranslationSubOrderChargeItemInput
import crud
import translation_customer_finance as finance
import customer_translation_rates as references


def test_leaf_fixed_price_ignores_counts_and_customer_reference_changes(environment, allowed):
    db, (user, _, _) = environment
    client, root, child, leaf = context(db, user)
    references.write_library(db, user, client.id, [item()], references.library(db, client.id)['version']); db.commit()
    version = finance.read(db, root.id)['version']
    result = finance.save(db, user, root.id, finance.PriceWrite(version=version, order_id=leaf.id, pricing_mode='fixed', adjusted_total='500', adjusted_total_incl_tax='530', currency='CNY'))
    assert result['item']['pricing_mode'] == 'aggregate'
    assert result['item']['children'][0]['children'][0]['pricing_mode'] == 'fixed'
    assert result['item']['children'][0]['children'][0]['prices'] == []
    assert result['item']['totals_excl_tax'] == {'CNY': '500.00'}
    assert result['item']['totals_incl_tax'] == {'CNY': '530.00'}
    assert result['item']['quantity'] is None
    refs = references.library(db, client.id)
    references.write_library(db, user, client.id, [item(amount='2')], refs['version']); db.commit()
    result = finance.read(db, root.id)['item']
    assert result['pricing_mode'] == 'aggregate' and result['totals_incl_tax'] == {'CNY': '530.00'}
    fixed = next(row for row in leaf.customer_charge_items if row.pricing_mode == 'fixed')
    assert fixed.unit_price_excl_tax is None and fixed.unit_price_incl_tax is None


@pytest.mark.parametrize('use_child',[False,True])
def test_project_form_preserves_company_count_basis_language_and_both_tax_prices(environment,use_child):
    from word_count_models import WordCountMetric
    db, (user, _, _) = environment
    _, root, child, leaf = context(db, user)
    owner=child if use_child else root
    # 有下级时以末级订单汇总；父级历史统计不参与当前计费。
    db.add(WordCountMetric(id=uuid4(), sub_order_id=leaf.id, dimension='company', metric_type='words', count_value=50)); db.commit()
    def assign_id(mapper, connection, target):
        if target.id is None: target.id=uuid4()
    event.listen(TranslationSubOrderChargeItem, 'before_insert', assign_id)
    try:
        crud._replace_customer_charge_items(db, owner, [TranslationSubOrderChargeItemInput(
            item_name='翻译费', pricing_mode='metric', metric_type='words', quantity_basis='company_words',
            language_pair='英语→简中', unit_size=1, unit_price_excl_tax='2', unit_price_incl_tax='2.12', currency='CNY',
        )], customer_values={'foreign_words': 10})
        db.commit()
    finally:
        event.remove(TranslationSubOrderChargeItem, 'before_insert', assign_id)
    restored=crud.get_sub_order(db,child.id) if use_child else crud.get_translation_project(db, root.id)
    charge=restored.customer_charge_items[0]
    assert charge.quantity_basis == 'company_words'
    assert charge.language_pair == '英语→简中'
    assert charge.quantity == 50
    assert charge.calculated_total_excl_tax == Decimal('100')
    assert charge.calculated_total_incl_tax == Decimal('106')


@pytest.mark.parametrize('use_child', [False, True])
def test_project_form_rejects_stale_parent_count_when_children_have_no_count(environment, use_child):
    from word_count_models import WordCountMetric
    db, (user, _, _) = environment
    _, root, child, _ = context(db, user)
    owner = child if use_child else root
    db.add(WordCountMetric(id=uuid4(), project_id=None if use_child else root.id,
                           sub_order_id=child.id if use_child else None,
                           dimension='company', metric_type='words', count_value=50))
    db.commit()
    def assign_id(mapper, connection, target):
        if target.id is None: target.id = uuid4()
    event.listen(TranslationSubOrderChargeItem, 'before_insert', assign_id)
    try:
        with pytest.raises(ValueError, match='有效的项目字数统计项'):
            crud._replace_customer_charge_items(db, owner, [TranslationSubOrderChargeItemInput(
                item_name='翻译费', pricing_mode='metric', metric_type='words', quantity_basis='company_words',
                unit_size=1, unit_price_excl_tax='2', currency='CNY',
            )], customer_values={'foreign_words': 10})
    finally:
        db.rollback()
        event.remove(TranslationSubOrderChargeItem, 'before_insert', assign_id)
