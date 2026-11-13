from uuid import uuid4
from decimal import Decimal
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_translation_customer_finance import setup
from models import Client
from interpretation_models import InterpretationLanguage
from word_count_models import WordCountMetric
import customer_translation_rates as rates
import translation_customer_finance as finance


def context(db,owner):
    db.add_all([InterpretationLanguage(id=uuid4(),label=name,is_active=True) for name in ('英语','简中','日语')])
    client=Client(id=uuid4(),client_name='测试客户',client_short_name='测试')
    db.add(client);db.commit()
    root,child,third=setup(db,owner);root.client_id=client.id
    for row in (root,child,third):
        row.language_pair='英语→简中'
        db.add(WordCountMetric(id=uuid4(),project_id=row.id if row is root else None,sub_order_id=None if row is root else row.id,dimension='customer',metric_type='foreign_words',count_value=10))
    db.commit();return client,root,child,third


def item(direction='英语→简中',amount='.1',**extra):return rates.RateInput(language_pair=direction,amount=amount,metric=extra.pop('metric','foreign_words' if direction=='英语→简中' else 'characters_no_spaces'),**extra)


def write(db,owner,root,order,items,**extra):
    return finance.save(db,owner,root.id,finance.PriceWrite(version=finance.read(db,root.id)['version'],order_id=order.id,prices=items,**extra))


def test_mother_lists_missing_fields_for_children_outside_the_page(environment):
    from models import TranslationSubOrder

    db,(owner,_,_)=environment
    _,root,branch,leaf=context(db,owner)
    root.language_pair=None
    missing=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+'.002',
                                sub_project_name='未登记子订单')
    db.add(missing)
    db.commit()
    write(db,owner,root,leaf,[item(amount='0',tax_prices={'unit_price_incl_tax':'0'})])
    full=finance.read(db,root.id)['item']
    selections,total,_=finance.paginate_child_orders([full],0,1)
    page_item=finance.apply_order_page(full,selections[0])
    assert total==3
    assert [child['id'] for child in page_item['children']]==[str(branch.id)]
    assert page_item['missing_child_orders']=={
        'language_pair':[missing.sub_order_no],
        'word_count':[missing.sub_order_no],
        'unit_price':[missing.sub_order_no],
    }


def test_aggregate_shows_adjusted_totals_only_for_child_overrides(environment):
    from models import TranslationSubOrder

    db,(owner,_,_)=environment
    _,root,_,leaf=context(db,owner)
    sibling=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+'.002',
                                sub_project_name='同项目另一子订单',language_pair=leaf.language_pair)
    db.add(sibling)
    db.add(WordCountMetric(id=uuid4(),sub_order_id=sibling.id,dimension='customer',metric_type='foreign_words',count_value=10))
    db.commit()
    price=item(amount='1',tax_prices={'unit_price_excl_tax':'1','unit_price_incl_tax':'2'})
    write(db,owner,root,sibling,[price])
    result=write(db,owner,root,leaf,[price])['item']
    assert result['calculated_totals_excl_tax']=={'CNY':'20.00'}
    assert result['calculated_totals_incl_tax']=={'CNY':'40.00'}
    assert result['adjusted_totals_excl_tax']==result['adjusted_totals_incl_tax']=={}

    def update_child_adjustment(amount):
        current=finance.read(db,root.id)
        return finance.save_table_cell(db,owner,root.id,finance.TablePatch(
            version=current['version'],order_id=leaf.id,adjusted_total_incl_tax=amount,
        ))['item']

    result=update_child_adjustment(15)
    assert result['adjusted_totals_incl_tax']=={'CNY':'35.00'}
    assert finance.read(db,root.id)['item']['adjusted_totals_incl_tax']=={'CNY':'35.00'}

    result=update_child_adjustment(0)
    assert result['adjusted_totals_excl_tax']=={}
    assert result['children'][0]['adjusted_totals_incl_tax']=={'CNY':'0.00'}
    assert result['adjusted_totals_incl_tax']=={'CNY':'20.00'}
    assert result['calculated_totals_incl_tax']=={'CNY':'40.00'}
    assert update_child_adjustment(None)['adjusted_totals_incl_tax']=={}

    with pytest.raises(HTTPException,match='请在子订单填写'):
        write(db,owner,root,root,[price],adjusted_total='30')


@pytest.mark.parametrize('filled,empty', [('incl_tax', 'excl_tax'), ('excl_tax', 'incl_tax')])
def test_one_sided_tax_rate_stays_separate_after_reopen_and_inheritance(environment, filled, empty):
    from crud import get_sub_order
    from models import TranslationSubOrder

    db, (owner, _, _) = environment
    _, root, _, leaf = context(db, owner)
    filled_key, empty_key = f'unit_price_{filled}', f'unit_price_{empty}'
    amount = Decimal('0.25')
    write(db, owner, root, leaf, [item(amount=amount, tax_prices={filled_key: amount})])
    charge = leaf.customer_charge_items[0]
    assert getattr(charge, empty_key) is None
    # Reproduce older records where the compatibility field held either tax basis.
    charge.unit_price = amount
    db.commit()

    reopened = finance.read(db, root.id)['item']['children'][0]['children'][0]
    price = reopened['prices'][0]
    assert Decimal(price['tax_prices'][filled_key]) == amount
    assert price['tax_prices'][empty_key] is None
    assert reopened[f'totals_{filled}'] == {'CNY': '2.50'}
    assert reopened[f'totals_{empty}'] == {}

    project_form_charge = get_sub_order(db, leaf.id).customer_charge_items[0]
    assert getattr(project_form_charge, empty_key) is None
    assert getattr(project_form_charge, f'calculated_total_{empty}') is None

    child = TranslationSubOrder(id=uuid4(), parent_project_id=root.id, sub_order_no=leaf.sub_order_no + '.001',
                                sub_project_name='继承税口径', language_pair=leaf.language_pair)
    db.add(child)
    finance.inherit_new_order(db, child)
    inherited = child.customer_charge_items[0]
    assert getattr(inherited, filled_key) == amount
    assert getattr(inherited, empty_key) is None


def test_blank_project_rate_matches_customer_basis_and_manual_price_stays_detached(environment):
    db, (owner, _, _) = environment
    client, root, _, leaf = context(db, owner)
    library = rates.write_library(db, owner, client.id, [item(metric='customer_auto:foreign_words')],
                                  rates.library(db, client.id)['version'])
    db.commit()

    def set_price(metric, amount=None):
        current = finance.read(db, root.id)
        result = finance.save_table_cell(db, owner, root.id, finance.TablePatch(
            version=current['version'], order_id=leaf.id,
            prices=[{'language_pair':'英语→简中','metric':metric,'amount':amount}],
        ))
        return result['item']['children'][0]['children'][0]['prices'][0]

    assert set_price('company_foreign_words')['amount'] is None
    adopted = set_price('customer_auto:foreign_words')
    assert adopted['reference_id'] == library['items'][0]['id']
    assert Decimal(adopted['amount']) == Decimal('.1')
    assert set_price('customer_auto:foreign_words', '.1')['reference_id'] is None
    rates.write_library(db, owner, client.id, [item(metric='customer_auto:foreign_words', amount='.2')],
                        library['version'])
    db.commit()
    latest = finance.read(db, root.id)['item']['children'][0]['children'][0]['prices'][0]
    assert Decimal(latest['amount']) == Decimal('.1')
    assert latest['reference_id'] is None


@pytest.mark.parametrize('direction,metric',[('英语→简中','foreign_words'),('简体中文→英语','characters_no_spaces'),('日语→繁體中文','foreign_words'),('zh-CN→英语','characters_no_spaces')])
def test_defaults(direction,metric):assert rates.default_metric(direction)=='customer_auto'


def test_library_direction_validation_version_and_history(environment):
    db,(owner,_,_)=environment;client,root,_,_=context(db,owner)
    initial=rates.library(db,client.id)
    result=rates.write_library(db,owner,client.id,[item(),item('简中→英语','.2')],initial['version']);db.commit()
    assert len(result['items'])==2 and result['items'][0]['updated_at'].endswith('+08:00')
    assert db.query(rates.CustomerTranslationRateHistory).count()==1
    with pytest.raises(HTTPException) as stale:rates.write_library(db,owner,client.id,[item()],initial['version'])
    assert stale.value.status_code==409;db.rollback()
    with pytest.raises(HTTPException) as duplicate:rates.write_library(db,owner,client.id,[item(),item(amount='.2')],result['version'])
    assert duplicate.value.status_code==422;db.rollback()
    with pytest.raises(HTTPException):rates.normalize(db,item('不存在→简中'))


def test_multirates_inheritance_and_metrics(environment):
    db,(owner,_,_)=environment;client,root,child,third=context(db,owner)
    root.language_pair='英语→简中；简中→英语';db.commit()
    result=write(db,owner,root,root,[item(),item('简中→英语','.2')])
    assert len(result['item']['prices'])==1  # 父级只显示下级实际采用的方向
    assert len(result['item']['recorded_prices'])==2
    assert result['item']['totals']=={'CNY':'1.00'}
    leaf=result['item']['children'][0]['children'][0]
    assert len(leaf['prices'])==1 and leaf['prices'][0]['metric']=='foreign_words'
    result=write(db,owner,root,third,[item(amount='.5')])
    assert result['item']['totals']=={'CNY':'5.00'}
    result=write(db,owner,root,root,[item(amount='.3'),item('简中→英语','.4')])
    assert result['item']['children'][0]['children'][0]['prices'][0]['amount']=='0.5'


def test_automatic_customer_sync_and_confirmed_project_sync(environment,monkeypatch):
    db,(owner,_,_)=environment;client,root,_,_=context(db,owner)
    library=rates.write_library(db,owner,client.id,[item()],rates.library(db,client.id)['version']);db.commit()
    ref=library['items'][0]
    adopted=item(reference_id=ref['id'],reference_revision=ref['revision'])
    result=write(db,owner,root,root,[adopted])
    rates.write_library(db,owner,client.id,[item(amount='.2')],rates.library(db,client.id)['version']);db.commit()
    assert finance.read(db,root.id)['item']['prices'][0]['amount']=='0.2'
    with pytest.raises(HTTPException) as stale:write(db,owner,root,root,[adopted])
    assert stale.value.status_code==409;db.rollback()
    monkeypatch.setattr(finance,'user_has_permission',lambda *a:True)
    updated=write(db,owner,root,root,[item(amount='.4')],update_library=True,sync_confirmed=True,library_version=rates.library(db,client.id)['version'])
    assert Decimal(updated['reference_prices']['items'][0]['amount'])==Decimal('.4')
    assert db.query(rates.CustomerTranslationRateHistory).filter_by(origin='project').count()==1


def test_library_sync_permission_and_foreign_charge(environment,monkeypatch):
    db,(owner,_,_)=environment;client,root,_,_=context(db,owner)
    monkeypatch.setattr(finance,'user_has_permission',lambda *a:False)
    with pytest.raises(HTTPException) as denied:write(db,owner,root,root,[item()],update_library=True,sync_confirmed=True,library_version=rates.library(db,client.id)['version'])
    assert denied.value.status_code==403;db.rollback()
    with pytest.raises(HTTPException) as foreign:write(db,owner,root,root,[item(id=uuid4())])
    assert foreign.value.status_code==422


def test_create_only_repeatable_migration(environment):
    from tools.apply_customer_translation_rates_migration import apply_migration
    db,_=environment
    for model in (rates.CustomerTranslationRateHistory,rates.TranslationChargeDirection,rates.CustomerTranslationRate):model.__table__.drop(db.connection())
    apply_migration(db.connection());apply_migration(db.connection())
    assert db.connection().dialect.has_table(db.connection(),'customer_translation_rate')


def test_reference_adoption_matches_physical_unit_and_sync_preserves_company_mode(environment,monkeypatch):
    db,(owner,_,_)=environment;client,root,_,leaf=context(db,owner)
    db.add(WordCountMetric(id=uuid4(),sub_order_id=leaf.id,dimension='company',metric_type='words',count_value=5));db.commit()
    lib=rates.write_library(db,owner,client.id,[item(metric='customer_auto:words',amount='.3')],rates.library(db,client.id)['version']);db.commit()
    ref=lib['items'][0]
    result=write(db,owner,root,leaf,[item(metric='company_words',amount='.3',reference_id=ref['id'],reference_revision=ref['revision'])])
    assert result['item']['children'][0]['children'][0]['prices'][0]['metric']=='company_words'
    with pytest.raises(HTTPException):write(db,owner,root,leaf,[item(metric='company_pages',amount='.3',reference_id=ref['id'],reference_revision=ref['revision'])])
    db.rollback()
    monkeypatch.setattr(finance,'user_has_permission',lambda *a:True)
    write(db,owner,root,leaf,[item(metric='company_words',amount='.4')],update_library=True,sync_confirmed=True,library_version=rates.library(db,client.id)['version'])
    lib=rates.library(db,client.id)
    assert len(lib['items'])==1 and lib['items'][0]['metric']=='customer_auto:words'
    rates.write_library(db,owner,client.id,[item(metric='customer_auto:words',amount='.5')],lib['version']);db.commit()
    loaded=finance.read(db,root.id)['item']['children'][0]['children'][0]
    assert loaded['prices'][0]['metric']=='company_words'
    assert Decimal(loaded['prices'][0]['amount'])==Decimal('.5')
