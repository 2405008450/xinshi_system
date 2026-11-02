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


def test_translation_manual_override_diff_and_confirmed_sync(environment,allowed):
    db,(user,_,_)=environment
    client,root,child,leaf=context(db,user)
    library=rates.write_library(db,user,client.id,[item()],rates.library(db,client.id)['version']);db.commit()
    assert written.read(db,root.id)['item']['prices'][0]['amount']=='0.1'
    write(db,user,root,leaf,[item(amount='.8')],adjusted_total='15',explanation='独立金额')
    rates.write_library(db,user,client.id,[item(amount='.2')],library['version']);db.commit()
    result=written.read(db,root.id)['item']
    assert result['prices'][0]['amount']=='0.2'
    assert result['children'][0]['children'][0]['prices'][0]['amount']=='0.8'
    diff=sync.differences('translation',client.id,page=1,db=db,user=user)
    assert diff['total']==1
    row=diff['items'][0]
    request=sync.SyncWrite(**{k:row[k] for k in ('project_id','order_id','version','customer_version')},direction='client_to_project')
    with pytest.raises(HTTPException) as unconfirmed:sync.sync('translation',client.id,request,db=db,user=user)
    assert unconfirmed.value.status_code==422
    sync.sync('translation',client.id,request.model_copy(update={'confirmed':True}),db=db,user=user)
    leaf_result=written.read(db,root.id)['item']['children'][0]['children'][0]
    assert leaf_result['prices'][0]['amount']=='0.2'
    assert Decimal(leaf_result['adjusted_total'])==15 and leaf_result['explanation']=='独立金额'
    assert sync.differences('translation',client.id,page=1,db=db,user=user)['total']==0
    with pytest.raises(HTTPException) as stale:sync.sync('translation',client.id,request.model_copy(update={'confirmed':True}),db=db,user=user)
    assert stale.value.status_code==409


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
