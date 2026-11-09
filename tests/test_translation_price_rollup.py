from uuid import uuid4
from decimal import Decimal
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_customer_translation_rates import context
from models import TranslationSubOrder,TranslationSubOrderChargeItem
from word_count_models import WordCountMetric
from word_count_schemas import WordCountMatrixResponse,WordCountMatrixPatch
from word_count_service import get_word_count_matrix,patch_word_count_matrix
import translation_customer_finance as finance

@pytest.fixture
def data(environment):
    db,(actor,*_)=environment;_,root,middle,leaf=context(db,actor)
    page=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=middle.sub_order_no+'.002',sub_project_name='按份收费',language_pair=leaf.language_pair)
    sibling=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+'.002',sub_project_name='另一字数单价',language_pair=leaf.language_pair)
    db.add_all([page,sibling]);db.flush()
    db.query(WordCountMetric).filter(WordCountMetric.project_id==root.id).delete()
    for node in (middle,leaf,page,sibling):db.query(WordCountMetric).filter(WordCountMetric.sub_order_id==node.id).delete()
    for node,metric,count in [(leaf,'words',100),(page,'documents',2),(sibling,'words',50)]:
        for dimension in ('customer','company'):db.add(WordCountMetric(id=uuid4(),sub_order_id=node.id,dimension=dimension,metric_type=metric,count_value=count))
    db.commit()
    def save(node,amount,incl,adjust=None):
        return finance.save(db,actor,root.id,finance.PriceWrite(version=finance.read(db,root.id)['version'],order_id=node.id,prices=[dict(language_pair=leaf.language_pair,metric='customer_auto',amount=amount,currency='CNY',unit_size=1,tax_prices={'unit_price_excl_tax':amount,'unit_price_incl_tax':incl})],adjusted_total=adjust))
    save(leaf,.2,.22,18);save(page,10,11);save(sibling,.3,.33)
    return db,actor,root,middle,leaf,page,sibling

def test_independent_statistics_keep_finance_price_rollup_without_double_counting(data):
    db,_,root,middle,leaf,page,sibling=data
    matrix=get_word_count_matrix(db,'project',root.id)
    assert matrix['source']=='project'
    assert matrix['customer']['words'] is None and matrix['customer']['documents'] is None
    WordCountMatrixResponse.model_validate(matrix)
    node=finance.read(db,root.id)['item'];mid=node['children'][0]
    assert node['price_aggregate'] and mid['price_aggregate']
    assert len(mid['prices'])==2 and len(node['prices'])==3
    assert {price['quantity_metric'] for price in node['prices']}=={'words','documents'}
    assert {source['id'] for price in node['prices'] for source in price['source_orders']}=={str(leaf.id),str(page.id),str(sibling.id)}
    assert node['calculated_totals_excl_tax']=={'CNY':'55.00'}
    assert node['totals_excl_tax']=={'CNY':'53.00'}
    assert node['totals_incl_tax']=={'CNY':'60.50'}
    assert mid['calculated_totals_excl_tax']=={'CNY':'40.00'} and mid['totals_excl_tax']=={'CNY':'38.00'}
    assert not root.customer_charge_items and not middle.customer_charge_items

def test_leaf_edit_updates_all_ancestors_and_parent_http_writes_are_rejected(data):
    db,actor,root,middle,leaf,page,sibling=data
    current=finance.read(db,root.id)
    with pytest.raises(HTTPException):finance.update(root.id,finance.PriceWrite(version=current['version'],order_id=middle.id,amount=1),db,actor)
    with pytest.raises(HTTPException):finance.save_table_cell(db,actor,root.id,finance.TablePatch(version=current['version'],order_id=root.id,adjusted_total=1))
    result=finance.save_table_cell(db,actor,root.id,finance.TablePatch(version=current['version'],order_id=leaf.id,prices=[dict(language_pair=leaf.language_pair,metric='customer_auto',amount=.4,currency='CNY',unit_size=1,tax_prices={'unit_price_excl_tax':.4,'unit_price_incl_tax':.44})]))
    assert result['item']['calculated_totals_excl_tax']=={'CNY':'75.00'}
    assert result['item']['totals_excl_tax']=={'CNY':'53.00'}
    assert any(Decimal(row['amount'])==Decimal('.4') for row in result['item']['prices'])
    db.add(WordCountMetric(id=uuid4(),project_id=root.id,dimension='customer',metric_type='words',count_value=1));db.commit()
    saved=patch_word_count_matrix(db,'project',root.id,WordCountMatrixPatch(changes=[dict(scope='entity',dimension='customer',metric_type='words',value=999)]),updated_by=actor.id)
    assert saved['customer']['words']==999
    assert finance.read(db,root.id)['item']['calculated_totals_excl_tax']=={'CNY':'75.00'}

def test_legacy_parent_override_is_retained_but_not_added_twice(data):
    db,_,root,_,_,_,_=data
    stored=TranslationSubOrderChargeItem(id=uuid4(),translation_project_id=root.id,sequence_no=1,item_name='翻译费',pricing_mode='fixed',currency='CNY',total_excl_tax=999)
    root.customer_charge_items.append(stored);db.commit()
    node=finance.read(db,root.id)['item']
    assert node['totals_excl_tax']=={'CNY':'53.00'} and node['recorded_adjusted_total']=='999'
    assert stored.total_excl_tax==999
