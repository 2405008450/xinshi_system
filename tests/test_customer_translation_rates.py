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
