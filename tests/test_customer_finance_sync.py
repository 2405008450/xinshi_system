"""只使用隔离 SQLite，验证自动下发、人工确认、差异和并发版本。"""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_customer_translation_rates import context, item, write
import customer_translation_rates as rates
import translation_customer_finance as written
import interpretation_customer_finance as oral
import customer_finance_sync as sync


@pytest.fixture
def allowed(monkeypatch):
    monkeypatch.setattr(sync,'user_has_permission',lambda *_:True)
    monkeypatch.setattr(oral,'user_has_permission',lambda *_:True)


def test_unfilled_translation_prices_are_not_differences_but_zero_is(environment, allowed):
    from models import TranslationSubOrderChargeItem
    db,(user,_,_)=environment
    client,root,child,leaf=context(db,user)
    for owner,amount in ((child,None),(leaf,Decimal('0'))):
        db.add(TranslationSubOrderChargeItem(
            id=uuid4(),sub_order_id=owner.id,pricing_mode='metric',currency='CNY',
            metric_type='foreign_words',unit_size=1,unit_price=amount,
        ))
    db.commit()
    result=sync.differences('translation',client.id,page=1,db=db,user=user)
    assert {row['order_id'] for row in result['items']}=={str(leaf.id)}
    grouped=sync.differences('translation',client.id,page=1,db=db,user=user,group_orders=True)
    assert grouped['difference_count']==1
    assert grouped['items'][0]['children'][0].get('project_rates') is None


def test_document_requirements_automatically_sync_in_both_directions(environment):
    import customer_statements as statements
    db,(user,_,_)=environment
    client,root,_,_=context(db,user)
    _,peer,_,_=context(db,user)
    peer.client_id=client.id
    db.commit()
    written.save(db,user,root.id,written.PriceWrite(
        version=written.read(db,root.id)['version'],order_id=root.id,documents_only=True,
        quotation_required=True,statement_required=True,invoice_required=True,
    ))
    preference=statements.client_preference(db,client.id)
    assert preference['quotation_required'] and preference['invoice_required']
    assert preference['statement_default']=='required'
    node=written.read(db,peer.id)['item']
    assert node['quotation_required'] and node['statement_required'] and node['invoice_required']
    statements.save_preference(client.id,statements.PreferenceWrite(
        revision=preference['revision'],tax_included=False,
        quotation_required=False,statement_default='not_required',invoice_required=False,
    ),db=db,user=user)
    for project in (root,peer):
        node=written.read(db,project.id)['item']
        assert not node['quotation_required'] and not node['statement_required'] and not node['invoice_required']


def test_translation_order_versions_and_latest_customer_rate(environment,allowed):
    db,(user,_,_)=environment
    client,root,child,leaf=context(db,user)
    rates.write_library(db,user,client.id,[item()],rates.library(db,client.id)['version']);db.commit()
    write(db,user,root,leaf,[item(amount='.8')],adjusted_total='15',explanation='independent total')
    write(db,user,root,leaf,[item(amount='.9')],adjusted_total='15',explanation='independent total')
    write(db,user,root,child,[item(amount='.7')])
    assert Decimal(rates.library(db,client.id)['items'][0]['amount'])==Decimal('.7')
    assert Decimal(rates.order_rates(db,leaf)[0]['amount'])==Decimal('.7')
    assert sync.differences('translation',client.id,page=1,db=db,user=user)['total']==0
    entries=rates.history(client.id,page=1,db=db)['items']
    assert any(event.get('action')=='automatic_project_sync' for event in entries)
    latest=rates.library(db,client.id)
    rates.write_library(db,user,client.id,[item(amount='.2')],latest['version']);db.commit()
    result=written.read(db,root.id)['item']['children'][0]['children'][0]
    assert Decimal(result['prices'][0]['amount'])==Decimal('.2')
    assert Decimal(result['adjusted_total'])==15 and result['explanation']=='independent total'
    with pytest.raises(HTTPException) as stale:
        rates.write_library(db,user,client.id,[item(amount='.3')],latest['version'])
    assert stale.value.status_code==409


def test_sub_customer_reference_priority_and_bidirectional_sync(environment,allowed):
    from models import SubClient
    from tools.apply_sub_client_translation_rate_migration import apply_migration
    db,(user,_,_)=environment
    client,root,_,leaf=context(db,user)
    apply_migration(db.connection())
    child=SubClient(id=uuid4(),parent_client_id=client.id,sub_client_code='SUB-REF',client_name='child',client_short_name='child')
    db.add(child);root.sub_client_id=child.id;db.commit()
    def set_price(amount,sub_id=None):
        rates.write_library(db,user,client.id,[item(amount=amount)],rates.library(db,client.id,sub_id)['version'],sub_client_id=sub_id)
        db.commit()
    write(db,user,root,leaf,[item(amount='.1')])
    set_price('.1');set_price('.2',child.id);set_price('.3')
    assert Decimal(rates.order_rates(db,leaf)[0]['amount'])==Decimal('.2')
    write(db,user,root,leaf,[item(amount='.9')])
    assert Decimal(rates.library(db,client.id,child.id)['items'][0]['amount'])==Decimal('.9')
    assert Decimal(rates.library(db,client.id)['items'][0]['amount'])==Decimal('.3')
    set_price('.4',child.id)
    assert Decimal(rates.order_rates(db,leaf)[0]['amount'])==Decimal('.4')
    history=rates.history(client.id,page=1,db=db,sub_client_id=child.id)['items']
    assert any(event['action']=='automatic_project_sync' for event in history)
    assert all(event['created_at'].endswith('+08:00') for event in history)


def test_translation_differences_match_effective_basis_and_numeric_size():
    from types import SimpleNamespace

    reference = {'id':'rate', 'revision':1, 'language_pair':'英→中', 'metric':'customer_auto:foreign_words',
                 'currency':'CNY', 'amount':'0.1000', 'unit_size':'1.0000'}
    row = dict(reference, metric='foreign_words', amount='0.1', unit_size='1')
    matrix = {'customer':{'characters_no_spaces':12, 'foreign_words':8}}
    owner = SimpleNamespace(language_pair='英→中', word_count_matrix=matrix)
    matching = sync.matching('translation', owner, owner, [row], [reference])
    assert sync.translation_rates_agree([row], matching, matrix)
    assert not sync.translation_rates_agree([dict(row, amount='0.2')], matching, matrix)
    assert not sync.translation_rates_agree([dict(row, unit_size='2')], matching, matrix)
    assert not sync.translation_rates_agree([dict(row, metric='company_foreign_words')], matching, matrix)
    assert not sync.translation_rates_agree([dict(row, tax_prices={'unit_price_incl_tax':'0.1'})], matching, matrix)


def test_mixed_order_tree_folds_only_siblings_with_the_same_direction():
    from types import SimpleNamespace

    owners=[SimpleNamespace(id=key, project_name=key) for key in ('root','a','b','c','nested')]
    numbers={owner.id:owner.id for owner in owners}
    parents={'a':'root','b':'root','c':'root','nested':'a'}
    directions={'root':{'英→中','日→中'},'a':{'英→中'},'b':{'英→中'},'c':{'日→中'},'nested':{'英→中'}}
    differences=[dict(order_id=key,order_no=key,project_name=key) for key in ('b','c','nested')]
    result=sync.translation_difference_tree(owners,numbers,parents,directions,differences)
    assert result['expand_by_default']
    group, separate=result['children']
    assert group['direction_group'] and group['language_directions']==['英→中']
    assert [child['order_id'] for child in group['children']]==['a','b']
    assert group['children'][0]['children'][0]['order_id']=='nested'
    assert separate['order_id']=='c'


def test_empty_order_uses_only_unique_matching_direction_and_effective_statistics():
    from translation_rate_matching import references_for_new_prices

    customer = {'language_pair':'英语→简中','metric':'customer_auto:words','unit_size':'1000'}
    company = {**customer, 'metric':'company_words'}
    other = {**customer, 'language_pair':'日语→简中'}
    assert references_for_new_prices([customer,company,other],'英语→简中',{'customer':{'words':20}})==[customer]
    assert references_for_new_prices([customer,company],'英语→简中',{'company':{'words':20}})==[company]
    assert references_for_new_prices([customer],'英语→简中',{'customer':{'characters_no_spaces':20,'words':10}})==[]


def test_automatic_basis_compares_selected_unit_and_shows_it_for_real_differences(environment,allowed):
    from word_count_models import WordCountMetric

    db,(user,_,_)=environment
    client,root,_,leaf=context(db,user)
    db.query(WordCountMetric).filter_by(sub_order_id=leaf.id).filter(WordCountMetric.metric_type!='foreign_words').delete()
    db.commit()
    refs=[item(metric='customer_auto:foreign_words'),item(metric='customer_auto:pages',amount='1')]
    rates.write_library(db,user,client.id,refs,rates.library(db,client.id)['version']);db.commit()
    write(db,user,root,leaf,[item(metric='customer_auto')])
    matched=sync.differences('translation',client.id,page=1,db=db,user=user)
    assert matched['total']==0,matched['items']

    write(db,user,root,leaf,[item(metric='customer_auto',amount='.3')])
    diff=sync.differences('translation',client.id,page=1,db=db,user=user)
    assert diff['total']==0
    matching=sync.matching('translation',root,leaf,rates.order_rates(db,leaf),rates.library(db,client.id)['items'])
    assert any(Decimal(ref['amount'])==Decimal('.3') for ref in matching)


def oral_setup(db):
    from models import Client
    from interpretation_models import InterpretationLanguage,InterpretationProject,InterpretationProjectLanguageDirection
    client=Client(id=uuid4(),client_name='口译同步客户')
    langs=[InterpretationLanguage(id=uuid4(),label=name) for name in ('英语','简中')]
    db.add_all([client,*langs]);db.flush()
    projects=[]
    for index in range(2):
        project=InterpretationProject(id=uuid4(),client_id=client.id,order_no=f'I-SYNC-{index}')
        project.language_directions=[InterpretationProjectLanguageDirection(id=uuid4(),source_language_id=langs[0].id,target_language_id=langs[1].id,sequence_no=1)]
        db.add(project);projects.append(project)
    db.commit()
    return client,projects


def oral_rate(amount=100,quantity=1):
    return dict(direction='英语 ↔ 简中',amount=amount,currency='CNY',unit='天',hours=8,quantity=quantity)


def test_oral_auto_sync_preserves_quantities_overtime_and_overrides(environment,allowed):
    db,(user,_,_)=environment
    client,projects=oral_setup(db)
    oral.save(db,user,'client',client.id,oral.FinanceWrite(revision=0,rates=[oral_rate()]))
    first=oral.context(db,'project',projects[0].id)
    assert first['payload']['rates'][0]['amount']=='100'
    oral.save(db,user,'project',projects[0].id,oral.FinanceWrite(revision=first['revision'],rates=[oral_rate(quantity=3)],
        has_overtime=True,overtime=dict(amount=50),adjusted_totals=[dict(amount=700)]))
    second=oral.context(db,'project',projects[1].id)
    oral.save(db,user,'project',projects[1].id,oral.FinanceWrite(revision=second['revision'],rates=[oral_rate(amount=150)]))
    assert oral.context(db,'client',client.id)['payload']['rates'][0]['amount']=='100' # 普通项目保存不得回写。
    oral.save(db,user,'client',client.id,oral.FinanceWrite(revision=1,rates=[oral_rate(amount=200)]))
    first=oral.context(db,'project',projects[0].id)
    assert first['payload']['rates'][0]['quantity']=='3'
    assert first['totals']=={'CNY':'650.00'} and first['adjusted_totals']=={'CNY':'700'}
    assert oral.context(db,'project',projects[1].id)['payload']['rates'][0]['amount']=='150'
    diff=sync.differences('interpretation',client.id,page=1,db=db,user=user)
    assert diff['total']==1
    row=diff['items'][0]
    request=sync.SyncWrite(**{k:row[k] for k in ('project_id','order_id','version','customer_version')},direction='project_to_client',confirmed=True)
    sync.sync('interpretation',client.id,request,db=db,user=user)
    assert oral.context(db,'client',client.id)['payload']['rates'][0]['amount']=='150'
    first=oral.context(db,'project',projects[0].id)
    assert first['payload']['rates'][0]['quantity']=='3' and first['totals']=={'CNY':'500.00'}
    assert sync.differences('interpretation',client.id,page=1,db=db,user=user)['total']==0


def test_sync_rejects_wrong_customer_permissions_and_stale_library(environment,allowed,monkeypatch):
    db,(user,_,_)=environment
    client,projects=oral_setup(db)
    oral.save(db,user,'client',client.id,oral.FinanceWrite(revision=0,rates=[oral_rate()]))
    project=oral.context(db,'project',projects[0].id)
    oral.save(db,user,'project',projects[0].id,oral.FinanceWrite(revision=project['revision'],rates=[oral_rate(amount=300)]))
    row=sync.differences('interpretation',client.id,page=1,db=db,user=user)['items'][0]
    request=sync.SyncWrite(**{k:row[k] for k in ('project_id','order_id','version','customer_version')},direction='project_to_client',confirmed=True)
    with pytest.raises(HTTPException) as stale:sync.sync('interpretation',client.id,request.model_copy(update={'customer_version':'0'}),db=db,user=user)
    assert stale.value.status_code==409
    other,_=oral_setup(db)
    with pytest.raises(HTTPException) as foreign:sync.sync('interpretation',other.id,request,db=db,user=user)
    assert foreign.value.status_code==422
    monkeypatch.setattr(sync,'user_has_permission',lambda *_:False)
    with pytest.raises(HTTPException) as denied:sync.sync('interpretation',client.id,request,db=db,user=user)
    assert denied.value.status_code==403


def test_oral_editor_backwrite_requires_confirmation_and_client_version(environment,allowed):
    db,(user,_,_)=environment
    client,projects=oral_setup(db)
    oral.save(db,user,'client',client.id,oral.FinanceWrite(revision=0,rates=[oral_rate()]))
    context=oral.context(db,'project',projects[0].id)
    request=oral.FinanceWrite(revision=context['revision'],rates=[oral_rate(amount=500)],update_library=True,library_revision=1)
    with pytest.raises(HTTPException) as unconfirmed:oral.put_context('project',projects[0].id,request,db=db,user=user)
    assert unconfirmed.value.status_code==422
    assert oral.context(db,'project',projects[0].id)['payload']['rates'][0]['amount']=='100'
    result=oral.put_context('project',projects[0].id,request.model_copy(update={'sync_confirmed':True}),db=db,user=user)
    assert result['payload']['rates'][0]['amount']=='500'
    assert oral.context(db,'client',client.id)['payload']['rates'][0]['amount']=='500'
