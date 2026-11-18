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


def test_translation_order_versions_and_latest_customer_rate(environment,allowed):
    from word_count_models import WordCountMetric

    db,(user,_,_)=environment
    client,root,child,leaf=context(db,user)
    db.query(WordCountMetric).filter(WordCountMetric.project_id==root.id,WordCountMetric.metric_type!='foreign_words').delete()
    db.query(WordCountMetric).filter(WordCountMetric.sub_order_id.in_([child.id,leaf.id]),WordCountMetric.metric_type!='foreign_words').delete()
    db.commit()
    library=rates.write_library(db,user,client.id,[item()],rates.library(db,client.id)['version']);db.commit()
    assert written.read(db,root.id)['item']['prices'][0]['amount']=='0.1'
    write(db,user,root,leaf,[item(amount='.8')],adjusted_total='15',explanation='独立金额')
    write(db,user,root,leaf,[item(amount='.9')],adjusted_total='15',explanation='独立金额')
    write(db,user,root,child,[item(amount='.7')])
    entries=rates.history(client.id,page=1,db=db)['items']
    order_entries=[event for event in entries if event['origin']=='order_rates']
    assert {(event['order_id'],event['revision']) for event in order_entries}=={
        (str(leaf.id),1),(str(leaf.id),2),(str(child.id),1)}
    assert {event['order_no'] for event in order_entries}=={leaf.sub_order_no,child.sub_order_no}
    assert Decimal(rates.library(db,client.id)['items'][0]['amount'])==Decimal('.1')
    assert sync.differences('translation',client.id,page=1,db=db,user=user)['total']==2
    grouped=sync.differences('translation',client.id,page=1,db=db,user=user,group_orders=True)
    assert (grouped['total'],grouped['difference_count'])==(1,2)
    mother=grouped['items'][0]
    assert mother['order_id']==str(root.id) and not mother.get('expand_by_default')
    assert mother['children'][0]['children'][0]['order_id']==str(leaf.id)

    rates.write_library(db,user,client.id,[item(amount='.2')],library['version']);db.commit()
    saved=written.read(db,root.id)['item']
    child_result=saved['children'][0]
    leaf_result=child_result['children'][0]
    assert rates.order_rates(db,child)[0]['amount']=='0.7'
    assert leaf_result['prices'][0]['amount']=='0.9'
    assert Decimal(leaf_result['adjusted_total'])==15 and leaf_result['explanation']=='独立金额'
    assert sync.differences('translation',client.id,page=1,db=db,user=user)['total']==2


def test_sub_customer_reference_priority_and_bidirectional_sync(environment, allowed):
    from models import SubClient
    from tools.apply_sub_client_translation_rate_migration import apply_migration

    db, (user, _, _) = environment
    client, root, _, leaf = context(db, user)
    apply_migration(db.connection())
    apply_migration(db.connection())
    child = SubClient(id=uuid4(), parent_client_id=client.id, sub_client_code='SUB-REF',
                      client_name='子客户', client_short_name='子客户')
    db.add(child)
    root.sub_client_id = child.id
    db.commit()

    def library(sub_id=None):
        return rates.library(db, client.id, sub_id)

    def set_price(amount, sub_id=None):
        rates.write_library(db, user, client.id, [item(amount=amount)], library(sub_id)['version'], sub_client_id=sub_id)
        db.commit()

    write(db, user, root, leaf, [item(amount='.1')])
    set_price('.1')
    set_price('.2', child.id)
    assert rates.order_rates(db, leaf)[0]['reference_id'] == library(child.id)['items'][0]['id']
    assert Decimal(rates.order_rates(db, leaf)[0]['amount']) == Decimal('.2')
    set_price('.3')
    assert Decimal(rates.order_rates(db, leaf)[0]['amount']) == Decimal('.2')

    write(db, user, root, leaf, [item(amount='.9')])
    set_price('.4', child.id)
    assert Decimal(rates.order_rates(db, leaf)[0]['amount']) == Decimal('.9')
    diff = sync.differences('translation', client.id, page=1, db=db, user=user, sub_client_id=child.id)
    assert any(row['order_id'] == str(leaf.id) for row in diff['items'])

    def confirm(direction, **kwargs):
        sync.sync('translation', client.id, sync.SyncWrite(
            project_id=root.id, order_id=leaf.id, version=written.read(db, root.id)['version'],
            customer_version=library(child.id)['version'], direction=direction, confirmed=True, **kwargs,
        ), db=db, user=user)

    confirm('client_to_project', sub_client_id=child.id)
    assert Decimal(rates.order_rates(db, leaf)[0]['amount']) == Decimal('.4')
    write(db, user, root, leaf, [item(amount='.9')])
    confirm('project_to_client')
    assert Decimal(library(child.id)['items'][0]['amount']) == Decimal('.9')
    assert Decimal(library()['items'][0]['amount']) == Decimal('.3')
    history = rates.history(client.id, page=1, db=db, sub_client_id=child.id)['items']
    manual_entry = next(event for event in history if event['action'] == 'manual_entry')
    assert manual_entry['actor_name'] == (user.full_name or user.username)
    assert manual_entry['before'] and manual_entry['after']
    for action in ('manual_project_sync', 'manual_order_sync', 'automatic_order_sync'):
        event = next(event for event in history if event['action'] == action and event['order_id'] == str(leaf.id))
        assert event['project_id'] == str(root.id) and event['order_no'] == leaf.sub_order_no
        assert event['created_at'].endswith('+08:00')
    assert all(event['id'] not in {entry['id'] for entry in history}
               for event in rates.history(client.id, page=1, db=db)['items'])


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
    assert diff['total']==1
    entry=diff['items'][0]
    price=entry['project_rates'][0]
    assert (price['metric'],price['quantity_dimension'],price['quantity_metric'])==('customer_auto','customer','foreign_words')
    request=sync.SyncWrite(**{key:entry[key] for key in ('project_id','order_id','version','customer_version')},direction='project_to_client',confirmed=True)
    sync.sync('translation',client.id,request,db=db,user=user)
    assert sync.differences('translation',client.id,page=1,db=db,user=user)['total']==0


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
