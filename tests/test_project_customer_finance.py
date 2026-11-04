from uuid import uuid4
from decimal import Decimal
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from tests.test_chat_participant_access import environment
from models import Client, SubClient
from database import get_db
from routers import auth
from annotation_models import AnnotationProject, AnnotationProjectPriceItem
from annotation_progress_time import business_now
from recruitment_models import RecruitmentProject
import project_customer_finance as finance
from tools.apply_project_customer_finance_migration import apply_migration

@pytest.fixture
def context(environment, monkeypatch):
    db, users = environment
    app = FastAPI(); app.include_router(finance.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: users[0]
    granted = {'projects:read', 'projects:write'}
    monkeypatch.setattr(auth, 'user_has_permission', lambda db, uid, code: code in granted)
    clients = [Client(id=uuid4(),client_code=f'CL-{i}',client_name=f'客户{i}',client_short_name=f'简称{i}') for i in range(2)]
    db.add_all(clients); db.commit()
    with TestClient(app) as http:
        yield http, db, users[0], clients, granted

def project(db, module, client, number='001'):
    now = business_now().replace(tzinfo=None)
    values = dict(id=uuid4(),order_no=f'TEST-{number}',project_name='Alpha Beta',client_id=client.id,project_status='project_in_progress',created_at=now,updated_at=now)
    if module == 'annotation':
        row=AnnotationProject(**values,priority='medium',status_effective_on=now,project_types=['audio_annotation'])
        row.price_items=[AnnotationProjectPriceItem(id=uuid4(),sequence_no=1,amount=Decimal('1.123456'),currency='CNY',unit='条',project_type='audio_annotation')]
    else:
        row=RecruitmentProject(**values,service_fee_amount=99,service_fee_currency='CNY')
    db.add(row);db.commit()
    return row

@pytest.mark.parametrize('module',['annotation','recruitment'])
def test_save_concurrency_history_and_permissions(context,module):
    http,db,user,clients,granted=context
    row=project(db,module,clients[0]); url=f'/project-customer-finance/{module}/project/{row.id}'
    initial=http.get(url); assert initial.status_code==200,initial.text
    data=initial.json(); assert data['totals_excl_tax']=={}
    tax={'unit_price_excl_tax':'1.123456','unit_price_incl_tax':'1.234567','total_excl_tax':'20.01','total_incl_tax':'21.23'}
    payload={'version':data['version'],'tax_prices':tax,'currency':'USD'}
    if module=='annotation':
        payload={'version':data['version'],'prices':[{k:v for k,v in data['prices'][0].items() if k not in ('tax_prices','language_display')}|{'tax_prices':tax,'currency':'USD'}]}
    result=http.put(url,json=payload);assert result.status_code==200,result.text
    assert result.json()['totals_excl_tax']=={'USD':'20.01'}
    assert result.json()['totals_incl_tax']=={'USD':'21.23'}
    db.expire_all()
    assert http.get(url).json()['version']==result.json()['version']
    assert http.put(url,json=payload).status_code==409
    history=http.get(url+'/history').json()
    assert history['total']==1 and history['items'][0]['actor_name']==user.full_name
    assert history['items'][0]['created_at'].endswith('+08:00')
    if module=='recruitment':
        assert row.service_fee_amount==99 and row.project_name=='Alpha Beta'
    granted.remove('projects:write')
    payload['version']=result.json()['version']
    assert http.put(url,json=payload).status_code==403
    assert http.get(url).status_code==200
    granted.remove('projects:read');assert http.get(url).status_code==403

@pytest.mark.parametrize('module',['annotation','recruitment'])
def test_filtered_pagination_totals_zero_and_sub_client(context,module):
    http,db,_,clients,_=context
    rows=[project(db,module,clients[0],str(i)) for i in range(3)]
    project(db,module,clients[1],'999')
    sub=SubClient(id=uuid4(),parent_client_id=clients[0].id,sub_client_code='SUB',client_name='分部',client_short_name='分部')
    db.add(sub);db.commit();rows[-1].client_id=None;rows[-1].sub_client_id=sub.id
    for index,row in enumerate(rows):
        target=row.price_items[0] if module=='annotation' else row
        target.tax_prices={'total_excl_tax':str(index),'total_incl_tax':'0'}
    db.commit()
    result=http.get(f'/project-customer-finance/{module}/page',params={'client_id':str(clients[0].id),'keyword':'BETA alpha','skip':1,'limit':1})
    assert result.status_code==200,result.text
    data=result.json();assert data['total']==3 and len(data['items'])==1
    assert Decimal(data['totals_excl_tax']['CNY'])==3 and Decimal(data['totals_incl_tax']['CNY'])==0
    assert data['items'][0]['client_id']==str(clients[0].id)
    assert http.get(f'/project-customer-finance/{module}/page',params={'keyword':'alpha missing'}).json()['total']==0

def test_annotation_rejects_other_project_price_and_language_scope(context):
    http,db,_,clients,_=context
    row=project(db,'annotation',clients[0]);other=project(db,'annotation',clients[0],'002')
    url=f'/project-customer-finance/annotation/project/{row.id}'
    initial=http.get(url).json();price=initial['prices'][0]
    for values in ({'id':str(other.price_items[0].id)},{'source_language_id':str(uuid4())},{'project_type':'text_annotation'}):
        assert http.put(url,json={'version':initial['version'],'prices':[price|values]}).status_code==422
    assert http.get(url+'/history').json()['total']==0

def test_migration_repeatable_only_new_table(environment):
    db,_=environment
    finance.ProjectCustomerFinanceHistory.__table__.drop(db.connection())
    before=set(inspect(db.connection()).get_table_names())
    apply_migration(db.connection());apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names())-before=={'project_customer_finance_history'}
