"""新增项目付款回归；仅使用内存 SQLite，不连接业务数据库。"""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from tests.test_chat_participant_access import environment
from tests.test_translation_direction_children import case
from schemas import TranslationProjectCreate, TranslationProjectUpdate
import translation_payment_service as payments


@pytest.mark.parametrize('version', ['', None, 'previous-project-version'])
@pytest.mark.parametrize('option', ['full', 'deposit'])
def test_create_with_initial_payment_uses_new_project_state(case, version, option):
    db, actor, crud = case
    receipt = dict(is_paid=True, payment_option=option, payment_account='测试收款账户', proofs='付款凭证备注')
    details = []
    if option == 'full':
        receipt.update(full_payment_amount=150, full_payment_total_key='billing:CNY')
    else:
        details = [dict(stage_type='deposit', actual_amount=50, payment_method='测试收款账户', proofs='付款凭证备注')]
    row = crud.create_translation_project(db, TranslationProjectCreate(
        project_name='付款回归.docx', created_by=actor.id,
        customer_charge_items=[dict(item_name='翻译费', pricing_mode='fixed', total_excl_tax=150)],
        payment_draft=details, payment_version=version, payment_confirmation=receipt,
    ), order_no='TP-261111-991')
    saved = payments.read(db, row)
    assert saved['confirmation']['revision'] == 1
    assert saved['confirmation']['payment_option'] == option
    assert saved['confirmation']['payment_account'] == '测试收款账户'
    assert saved['confirmation']['proofs'] == '付款凭证备注'
    if option == 'full':
        assert saved['confirmation']['full_match_status'] == 'matched'
        assert Decimal(saved['confirmation']['full_payment_amount']) == 150
        assert not saved['payments']
    else:
        assert len(saved['payments']) == 1
        assert Decimal(saved['payments'][0]['actual_amount']) == 50

    # 新增兼容不能绕过已有项目的版本保护，即使提交内容完全相同。
    for stale in ['', 'previous-project-version']:
        with pytest.raises(HTTPException) as conflict:
            crud.update_translation_project(db, row.id, TranslationProjectUpdate(
                payment_draft=saved['payments'], payment_version=stale,
                payment_confirmation=saved['confirmation'],
            ), actor.id)
        assert conflict.value.status_code == 409
        db.rollback()
    assert payments.read(db, row) == saved


def test_initial_full_payment_matches_final_child_total_without_details(case):
    db, actor, crud = case
    row = crud.create_translation_project(db, TranslationProjectCreate(
        project_name='母项目', created_by=actor.id, initial_sub_order_names=['子文件.docx'],
        customer_charge_items=[dict(item_name='翻译费', pricing_mode='fixed', total_excl_tax=999)],
        initial_sub_order_details={'001': {'customer_charge_items': [
            dict(item_name='翻译费', pricing_mode='fixed', total_excl_tax=150),
        ]}},
        payment_confirmation=dict(is_paid=True, payment_option='full', full_payment_amount=150,
                                  full_payment_total_key='billing:CNY'),
    ), order_no='TP-261111-992')
    saved = payments.read(db, row)
    assert saved['confirmation']['full_match_status'] == 'matched'
    assert Decimal(saved['confirmation']['full_reference_amount']) == 150


def test_invalid_initial_payment_rolls_back_entire_project(case):
    from models import TranslationProject, TranslationSubOrder, FinanceRecord
    from translation_payment_confirmation import TranslationPaymentConfirmationHistory
    db, actor, crud = case
    with pytest.raises(HTTPException) as invalid:
        crud.create_translation_project(db, TranslationProjectCreate(
            project_name='校验失败项目', created_by=actor.id, initial_sub_order_names=['子文件.docx'],
            payment_draft=[], payment_version='',
            payment_confirmation=dict(is_paid=True, payment_option='full', full_payment_amount=150),
        ), order_no='TP-261111-993')
    assert invalid.value.status_code == 422
    db.rollback()
    for model in (TranslationProject, TranslationSubOrder, FinanceRecord, TranslationPaymentConfirmationHistory):
        assert db.query(model).count() == 0
