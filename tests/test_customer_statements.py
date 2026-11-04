"""对账单隔离验证：不连接业务数据库，不写真实账户信息。"""
from base64 import b64decode
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import inspect
from tests.test_chat_participant_access import environment
from models import Client,TranslationProject,TranslationSubOrder,TranslationSubOrderChargeItem,SubClient
from word_count_models import WordCountMetric
from routers import auth
from database import get_db
import customer_statements as statements
from tools.apply_customer_statements_migration import apply_migration,TABLES

@pytest.fixture
def context(environment,monkeypatch):
    db,users=environment
    clients=[Client(id=uuid4(),client_code=f'CL-{i}',client_name=f'对账客户{i}',client_short_name=f'客户{i}') for i in range(2)]
    db.add_all(clients);db.commit()
    app=FastAPI();app.include_router(statements.router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[auth.get_current_user]=lambda:users[0]
    granted={'clients:read','clients:write','projects:read'}
    monkeypatch.setattr(auth,'user_has_permission',lambda db,uid,code:code in granted)
    monkeypatch.setattr(auth,'get_user_permission_codes',lambda db,uid:list(granted))
    with TestClient(app) as http:yield http,db,clients,granted,users[0]

def project(db,client,number='001',month='2026-11',fixed=False,currency='CNY'):
    row=TranslationProject(id=uuid4(),order_no=f'TP-261101-{number}',project_name='测试项目.docx',source_file_name='测试项目.docx',language_pair='英语→简中',client_id=client.id,
        customer_reception_time=datetime(2026,10,31,23,30),created_at=datetime(2026,11,1),updated_at=datetime(2026,11,1))
    charge=TranslationSubOrderChargeItem(id=uuid4(),sequence_no=1,item_name='翻译费',pricing_mode='fixed' if fixed else 'metric',currency=currency,
        metric_type=None if fixed else 'words',unit_size=None if fixed else 1000,unit_price_excl_tax=None if fixed else 100,
        unit_price_incl_tax=None if fixed else 106,total_excl_tax=500 if fixed else None,total_incl_tax=530 if fixed else None,
        billing_month=month,remarks='项目收费备注',created_at=datetime(2026,11,1),updated_at=datetime(2026,11,1))
    row.customer_charge_items=[charge];db.add(row)
    db.add(WordCountMetric(id=uuid4(),project_id=row.id,dimension='customer',metric_type='words',count_value=1234))
    db.commit();return row

def preview(http,row,**extra):
    return http.get('/translation-statements/preview',params={'project_id':str(row.id),'month':'2026-11',**extra})

def test_tax_preference_receipt_workload_and_month_scope(context):
    http,db,clients,_,_=context
    root=project(db,clients[0]);project(db,clients[0],'002',fixed=True);project(db,clients[0],'003','2026-10');project(db,clients[1],'004')
    first=preview(http,root);assert first.status_code==200,first.text
    data=first.json();assert len(data['rows'])==1
    row=data['rows'][0];assert row['received_date']=='2026-10-31' and row['unit_label']=='不含税'
    assert row['quantity']=='1234.0000' or Decimal(row['quantity'])==1234
    assert '字数' in row['basis'] and '1000' in row['basis']
    assert row['subtotal']=='123.40' and data['totals']=={'CNY':'123.40'}
    response=http.put(f'/clients/{clients[0].id}/statement-preference',json={'revision':0,'tax_included':True});assert response.status_code==200,response.text
    assert http.put(f'/clients/{clients[0].id}/statement-preference',json={'revision':0,'tax_included':False}).status_code==409
    monthly=preview(http,root,scope='customer').json()
    assert len(monthly['rows'])==2 and monthly['totals']=={'CNY':'660.80'}
    assert monthly['rows'][0]['unit_label']=='含税'
    assert not monthly['pending']
    assert http.get('/translation-statements/excel',params={'project_id':str(root.id),'month':'2026-11','version':data['statement_version']}).status_code==409
    assert preview(http,root,month='2026-12').json()['rows']==[]

def test_zero_unknown_currency_and_sub_client(context):
    http,db,clients,_,_=context
    root=project(db,clients[0]);zero=project(db,clients[0],'002',currency='USD')
    zero.customer_charge_items[0].unit_price_excl_tax=0
    sub=SubClient(id=uuid4(),parent_client_id=clients[0].id,sub_client_code='SUB1',client_name='分部',client_short_name='分部')
    db.add(sub);db.flush();zero.client_id=None;zero.sub_client_id=sub.id;db.commit()
    result=preview(http,root,scope='customer').json();assert result['totals']=={'CNY':'123.40','USD':'0.00'}
    root.customer_charge_items[0].unit_price_excl_tax=None;db.commit()
    result=preview(http,root).json();assert result['rows'][0]['subtotal'] is None and result['pending'] and result['totals']=={}

def test_hierarchy_not_double_counted_fixed_and_adjustments(environment):
    db,users=environment
    from tests.test_translation_customer_finance import setup,write
    root,child,third=setup(db,users[0]);client=Client(id=uuid4(),client_code='CL-TREE',client_name='树客户',client_short_name='树客户');db.add(client);root.client_id=client.id;db.commit()
    write(db,users[0],root,root,'0.5',billing_month='2026-11')
    data=statements.build_statement(db,root.id,None,'2026-11','project')
    assert len(data['rows'])==1 and data['rows'][0]['order_no']==third.sub_order_no and data['totals']=={'CNY':'10.00'}
    write(db,users[0],root,root,'0.5',adjusted_total=15,billing_month='2026-11')
    data=statements.build_statement(db,root.id,None,'2026-11','project');assert data['totals']=={'CNY':'15.00'}
    assert data['rows'][-1]['basis']=='总价调整'
    import translation_customer_finance as finance
    current=finance.read(db,root.id)
    finance.save(db,users[0],root.id,finance.PriceWrite(version=current['version'],order_id=root.id,pricing_mode='fixed',adjusted_total=30,billing_month='2026-11'))
    result=statements.build_statement(db,root.id,None,'2026-11','project');assert len(result['rows'])==1 and result['totals']=={'CNY':'30.00'}

def test_company_settings_stamp_validation_export_and_permissions(context):
    http,db,clients,granted,_=context
    root=project(db,clients[0]);settings=http.get('/customer-statement-settings').json()
    assert b64decode(settings['default_stamp'].split(',')[1]).startswith(b'\x89PNG')
    body={'revision':0,'bank_name':'测试银行','account_name':'测试公司','account_number':'001234567890','stamp_image':settings['default_stamp']}
    saved=http.put('/customer-statement-settings',json=body);assert saved.status_code==200,saved.text
    assert saved.json()['revision']==1
    assert http.put('/customer-statement-settings',json=body).status_code==409
    body['revision']=1;body['stamp_image']='data:image/svg+xml;base64,PHN2Zz4='
    assert http.put('/customer-statement-settings',json=body).status_code==422
    result=http.get('/translation-statements/excel',params={'project_id':str(root.id),'month':'2026-11'})
    assert result.status_code==200,result.text
    workbook=load_workbook(BytesIO(result.content));sheet=workbook.active
    assert sheet['A1'].value==statements.COMPANY and sheet['A2'].value=='对账单'
    assert sheet['A5'].value=='来稿日期' and sheet['E6'].value.endswith('（不含税）')
    assert any(cell.value=='账号：001234567890' for row in sheet for cell in row)
    with ZipFile(BytesIO(result.content)) as zipfile:
        assert 'xl/media/image1.png' in zipfile.namelist()
        assert b'<col>3</col>' in zipfile.read('xl/drawings/drawing1.xml') # 合计左侧的浮动图片图层。
    granted.remove('clients:write');assert http.put('/customer-statement-settings',json=body).status_code==403
    granted.remove('projects:read');assert preview(http,root).status_code==403

def test_migration_repeatable_without_old_table_changes(environment):
    db,_=environment
    for name in TABLES:statements.Base.metadata.tables[name].drop(db.connection())
    before=set(inspect(db.connection()).get_table_names())
    columns=[column['name'] for column in inspect(db.connection()).get_columns('client')]
    apply_migration(db.connection());apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names())-before==set(TABLES)
    assert columns==[column['name'] for column in inspect(db.connection()).get_columns('client')]


def test_order_display_preview_and_excel_do_not_double_count(context):
    http,db,clients,_,_=context
    root=project(db,clients[0])
    for suffix,amount in [('.001',None),('.001.001',10),('.002',20)]:
        child=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+suffix,sub_project_name='子订单'+suffix,language_pair='英语→简中')
        if amount is not None:child.customer_charge_items=[TranslationSubOrderChargeItem(id=uuid4(),sequence_no=1,item_name='翻译费',pricing_mode='fixed',currency='CNY',total_excl_tax=amount,total_incl_tax=Decimal(amount)*Decimal('1.06'),billing_month='2026-11')]
        db.add(child)
    db.commit()
    results={mode:preview(http,root,order_display=mode).json() for mode in ('parents','all','children')}
    for mode,data in results.items():
        assert data['order_display']==mode
        assert data['totals']=={'CNY':'30.00'}
        assert sum(Decimal(row['subtotal']) for row in data['rows'] if row.get('counted_in_total',True))==30
    assert [row['order_no'] for row in results['parents']['rows']]==[root.order_no]
    assert {row['order_no'] for row in results['children']['rows']}=={root.order_no+'.001.001',root.order_no+'.002'}
    assert {row['order_no'] for row in results['all']['rows']}=={root.order_no,root.order_no+'.001',root.order_no+'.001.001',root.order_no+'.002'}
    for mode,data in results.items():
        response=http.get('/translation-statements/excel',params={'project_id':str(root.id),'month':'2026-11','order_display':mode,'version':data['statement_version']})
        assert response.status_code==200,response.text
        sheet=load_workbook(BytesIO(response.content)).active
        assert sheet.cell(6+len(data['rows']),6).value=='CNY 30.00'
        if mode=='all':assert '汇总参考' in sheet['G6'].value
    assert preview(http,root,order_display='invalid').status_code==422
    assert http.get('/translation-statements/excel',params={'project_id':str(root.id),'month':'2026-11','order_display':'all','version':results['parents']['statement_version']}).status_code==409


def test_order_display_keeps_standalone_projects_and_currency_groups(context):
    http,db,clients,_,_=context
    root=project(db,clients[0]);project(db,clients[0],'002',fixed=True,currency='USD')
    for mode in ('parents','all','children'):
        result=preview(http,root,scope='customer',order_display=mode).json()
        assert len(result['rows'])==2
        assert result['totals']=={'CNY':'123.40','USD':'500.00'}
