"""财务表格按单元格保存；全部使用隔离内存库。"""
from uuid import uuid4
import pytest
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context, project
from interpretation_models import InterpretationLanguage
import translation_customer_finance as finance


@pytest.fixture
def table(context):
    http,db,clients,granted,user=context
    granted.add('projects:write');http.app.include_router(finance.router)
    db.add_all([InterpretationLanguage(id=uuid4(),label=label,is_active=True) for label in ('英语','简中')])
    root=project(db,clients[0]);db.commit()
    return http,db,root


def patch(http,root,**changes):
    before=http.get(f'/translation-customer-finance/project/{root.id}').json()
    response=http.patch(f'/translation-customer-finance/project/{root.id}/table',json={'version':before['version'],'order_id':str(root.id),**changes})
    assert response.status_code==200,response.text
    return response.json()


def test_metadata_can_save_without_unit_price_or_language_and_has_history(table):
    http,db,root=table
    root.customer_charge_items.clear();root.language_pair='';db.commit()
    result=patch(http,root,explanation='单元格直接填写')
    assert result['item']['explanation']=='单元格直接填写'
    assert result['item']['totals_excl_tax']=={}
    assert patch(http,root,billing_month='2026-12')['item']['billing_month']=='2026-11'
    history=http.get(f'/translation-customer-finance/project/{root.id}/history').json()
    assert history['total']==2


def test_fixed_mode_may_be_incomplete_then_zero_is_saved(table):
    http,_,root=table
    result=patch(http,root,pricing_mode='fixed')
    assert result['item']['pricing_mode']=='fixed'
    assert result['item']['totals_excl_tax']=={}
    from decimal import Decimal
    assert Decimal(patch(http,root,adjusted_total=0)['item']['totals_excl_tax']['CNY'])==0
    latest=http.get(f'/translation-customer-finance/project/{root.id}').json()
    full=http.put(f'/translation-customer-finance/project/{root.id}',json={'version':latest['version'],'order_id':str(root.id),'pricing_mode':'fixed'})
    assert full.status_code==422  # 完整编辑窗口仍校验必填金额。


def test_unit_prices_and_blank_prices_save_without_fabricated_zero(table):
    http,_,root=table
    price={'language_pair':'英语→简中','currency':'CNY','metric':'customer_auto','unit_size':1,'amount':None,'tax_prices':{'unit_price_excl_tax':None,'unit_price_incl_tax':None}}
    result=patch(http,root,prices=[price])
    assert result['item']['prices'][0]['amount'] is None
    assert result['item']['totals_excl_tax']=={}
    price.update(id=result['item']['prices'][0]['id'],amount=0.2,tax_prices={'unit_price_excl_tax':0.2,'unit_price_incl_tax':0.212})
    result=patch(http,root,prices=[price])
    assert result['item']['totals_excl_tax']=={'CNY':'246.80'}
    assert result['item']['totals_incl_tax']=={'CNY':'261.61'}


def test_stale_cell_edit_cannot_overwrite_and_unrelated_values_stay(table):
    http,_,root=table
    before=http.get(f'/translation-customer-finance/project/{root.id}').json()
    patch(http,root,explanation='先保存的说明')
    stale=http.patch(f'/translation-customer-finance/project/{root.id}/table',json={'version':before['version'],'order_id':str(root.id),'explanation':'过期内容'})
    assert stale.status_code==409
    result=patch(http,root,adjusted_total_incl_tax=150)
    assert result['item']['explanation']=='先保存的说明'
    assert result['item']['prices'][0]['amount']==before['item']['prices'][0]['amount']


def test_child_note_keeps_inherited_prices(table):
    from models import TranslationSubOrder
    from word_count_models import WordCountMetric
    http,db,root=table
    child=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+'.1',sub_project_name='子订单',language_pair=root.language_pair)
    db.add(child);db.add(WordCountMetric(id=uuid4(),sub_order_id=child.id,dimension='customer',metric_type='words',count_value=200));db.commit()
    before=http.get(f'/translation-customer-finance/project/{root.id}').json()
    old=before['item']['children'][0]
    response=http.patch(f'/translation-customer-finance/project/{root.id}/table',json={'version':before['version'],'order_id':str(child.id),'explanation':'子订单说明'})
    assert response.status_code==200,response.text
    current=response.json()['item']['children'][0]
    assert current['totals_excl_tax']==old['totals_excl_tax']
    assert current['prices'][0]['amount']==old['prices'][0]['amount']
    assert current['explanation']=='子订单说明'


def test_remove_last_price_keeps_notes_month_and_adjustment(table):
    http,_,root=table
    patch(http,root,explanation='保留说明',adjusted_total=5,billing_month='2026-12')
    result=patch(http,root,prices=[])
    assert result['item']['prices']==[]
    assert result['item']['explanation']=='保留说明'
    assert result['item']['billing_month']=='2026-11'
    assert result['item']['adjusted_total'] is not None
    result=patch(http,root,prices=[{'language_pair':'英语→简中','amount':0.2,'currency':'CNY','metric':'customer_auto'}])
    assert len(result['item']['prices'])==1
