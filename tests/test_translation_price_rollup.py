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


def test_finance_pagination_counts_child_orders_and_keeps_ancestor_context(data):
    db,actor,root,middle,leaf,document,sibling=data
    params=dict(db=db,user=actor,payment_project_id=root.id,billing_month=None,limit=2,paginate_children=True)
    first=finance.page(skip=0,**params)
    second=finance.page(skip=2,**params)
    assert first['total']==second['total']==4
    assert first['pagination_unit']=='child_orders'
    first_root=first['items'][0];second_root=second['items'][0]
    assert first_root['id']==second_root['id']==str(root.id)
    assert first_root['page_index'] is None and second_root['page_index'] is None
    first_middle=first_root['children'][0];second_middle=second_root['children'][0]
    assert first_middle['id']==second_middle['id']==str(middle.id)
    assert first_middle['page_index']==1 and second_middle['page_index'] is None
    assert [(node['id'],node['page_index']) for node in first_middle['children']]==[(str(leaf.id),2)]
    assert [(node['id'],node['page_index']) for node in second_middle['children']]==[(str(document.id),3)]
    assert (second_root['children'][1]['id'],second_root['children'][1]['page_index'])==(str(sibling.id),4)
    assert first['client_subtotals']==second['client_subtotals']
    assert first_root['totals_excl_tax']==second_root['totals_excl_tax']=={'CNY':'53.00'}

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


def test_parent_can_bill_directly_then_return_to_child_rollup(data):
    db, actor, root, middle, leaf, _, _ = data
    current = finance.read(db, root.id)
    switched = finance.save_table_cell(db, actor, root.id, finance.TablePatch(
        version=current['version'], order_id=middle.id, pricing_mode='fixed'))
    assert switched['item']['children'][0]['pricing_mode'] == 'fixed'
    fixed = finance.save_table_cell(db, actor, root.id, finance.TablePatch(
        version=switched['version'], order_id=middle.id, adjusted_total=70))
    assert fixed['item']['totals_excl_tax'] == {'CNY': '85.00'}
    assert fixed['item']['billing_totals'] == {'CNY': '85.00'}
    inherited = fixed['item']['children'][0]['children'][0]
    assert inherited['pricing_mode'] == 'fixed' and inherited['fixed_pricing_from'] == middle.sub_order_no
    assert inherited['prices'] == [] and inherited['totals_excl_tax'] == {}
    from customer_statements import build_statement
    statement = build_statement(db, root.id, None, finance.order_billing_month(root.order_no), 'project')
    assert statement['totals'] == {'CNY': '85.00'}
    assert str(leaf.id) not in {row['task_id'] for row in statement['rows']}

    # 母订单改为直接按量计费时，使用本单独立填报数量。
    patch_word_count_matrix(db,'project',root.id,WordCountMatrixPatch(changes=[
        {'scope':'entity','dimension':'customer','metric_type':'words','value':150}
    ]),updated_by=actor.id)
    workload = finance.update(root.id, finance.PriceWrite(
        version=finance.read(db,root.id)['version'], order_id=root.id, order_pricing_mode='metric',
        prices=[dict(language_pair=leaf.language_pair, metric='customer_auto:words', amount=1,
                     currency='CNY', unit_size=1, tax_prices={'unit_price_excl_tax': 1})]), db, actor)
    assert workload['item']['totals_excl_tax'] == {'CNY': '150.00'}
    assert workload['item']['billing_totals'] == {'CNY': '150.00'}
    assert workload['item']['children'][0]['totals_excl_tax'] == {'CNY': '70.00'}

    restored = finance.save_table_cell(db, actor, root.id, finance.TablePatch(
        version=workload['version'], order_id=root.id, pricing_mode='aggregate'))
    assert restored['item']['price_aggregate']
    assert restored['item']['totals_excl_tax'] == {'CNY': '85.00'}

    work_mode = finance.save_table_cell(db, actor, root.id, finance.TablePatch(
        version=restored['version'], order_id=middle.id, pricing_mode='metric'))
    assert work_mode['item']['children'][0]['pricing_mode'] == 'metric'
    assert work_mode['item']['children'][0]['children'][0]['totals_excl_tax'] == {'CNY': '18.00'}


def test_fixed_parent_cascades_without_replacing_descendant_prices(data):
    db, actor, root, middle, leaf, _, _ = data
    initial = finance.read(db, root.id)
    original_prices = initial['item']['children'][0]['children'][0]['prices']
    fixed = finance.update(root.id, finance.PriceWrite(
        version=initial['version'], order_id=root.id, order_pricing_mode='fixed',
        pricing_mode='fixed', adjusted_total=900,
    ), db, actor)
    listed = finance.page(db=db, user=actor, payment_project_id=root.id, billing_month=None, skip=0, limit=10)
    for item in (fixed['item'], listed['items'][0]):
        assert item['pricing_mode'] == 'fixed' and item['totals_excl_tax'] == {'CNY':'900.00'}
        for child in [*item['children'], *item['children'][0]['children']]:
            assert child['pricing_mode'] == 'fixed'
            assert child['fixed_pricing_from'] == root.order_no and child['prices'] == []
    with pytest.raises(HTTPException, match='继承上级固定收费'):
        finance.save_table_cell(db,actor,root.id,finance.TablePatch(
            version=fixed['version'],order_id=leaf.id,adjusted_total=10))
    db.rollback()
    restored = finance.save_table_cell(db, actor, root.id, finance.TablePatch(
        version=fixed['version'],order_id=root.id,pricing_mode='aggregate'))
    assert restored['item']['pricing_mode'] == 'aggregate'
    restored_leaf = restored['item']['children'][0]['children'][0]
    assert restored_leaf['pricing_mode'] == 'metric' and restored_leaf['fixed_pricing_from'] is None
    assert restored_leaf['prices'] == original_prices
    assert restored['item']['totals_excl_tax'] == initial['item']['totals_excl_tax']
