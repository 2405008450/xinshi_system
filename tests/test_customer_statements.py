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
    from statement_access import StatementGrant
    db.add_all([StatementGrant(user_id=users[0].id,client_id=client.id,edit_content=True,cross_client=False,revision=1,granted_by=users[0].id) for client in clients]);db.commit()
    app=FastAPI();app.include_router(statements.router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[auth.get_current_user]=lambda:users[0]
    granted={'clients:read','clients:write','projects:read'}
    monkeypatch.setattr(auth,'user_has_permission',lambda db,uid,code:code in granted)
    monkeypatch.setattr(auth,'get_user_permission_codes',lambda db,uid:list(granted))
    with TestClient(app) as http:yield http,db,clients,granted,users[0]

def project(db,client,number='001',month='2026-11',fixed=False,currency='CNY'):
    row=TranslationProject(id=uuid4(),order_no=f"TP-{month[2:4]}{month[5:7]}01-{number}",project_name='测试项目.docx',source_file_name='测试项目.docx',language_pair='英语→简中',client_id=client.id,
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
    result=preview(http,root).json();assert result['rows'][0]['subtotal']=='130.80' and result['rows'][0]['unit_label']=='含税' and not result['pending']
    root.customer_charge_items[0].unit_price_incl_tax=None;db.commit()
    result=preview(http,root).json();assert result['rows'][0]['subtotal'] is None and result['pending'] and result['totals']=={}

def test_hierarchy_not_double_counted_fixed_and_adjustments(environment):
    db,users=environment
    from tests.test_translation_customer_finance import setup,write
    root,child,third=setup(db,users[0]);client=Client(id=uuid4(),client_code='CL-TREE',client_name='树客户',client_short_name='树客户');db.add(client);root.client_id=client.id;db.commit()
    write(db,users[0],root,root,'0.5',billing_month='2026-11')
    data=statements.build_statement(db,root.id,None,'2026-11','project')
    assert len(data['rows'])==1 and data['rows'][0]['order_no']==third.sub_order_no and data['totals']=={'CNY':'10.00'}
    write(db,users[0],root,third,'0.5',adjusted_total=15,billing_month='2026-11')  # 末级调整，父级累计
    data=statements.build_statement(db,root.id,None,'2026-11','project');assert data['totals']=={'CNY':'15.00'}
    assert len(data['rows'])==1 and data['rows'][0]['order_no']==third.sub_order_no  # 末级调整直接体现为任务小计，不新增父级调整行
    import translation_customer_finance as finance
    current=finance.read(db,root.id)
    finance.save(db,users[0],root.id,finance.PriceWrite(version=current['version'],order_id=third.id,pricing_mode='fixed',adjusted_total=30,billing_month='2026-11'))
    result=statements.build_statement(db,root.id,None,'2026-11','project');assert len(result['rows'])==1 and result['totals']=={'CNY':'30.00'}

def test_company_settings_stamp_validation_export_and_permissions(context,monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
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
    assert sheet['A5'].value=='来稿日期' and sheet['E6'].value=='CNY 100.000'
    assert any(cell.value=='账号：001234567890' for row in sheet for cell in row)
    with ZipFile(BytesIO(result.content)) as zipfile:
        assert 'xl/media/image1.png' in zipfile.namelist()
        assert b'<col>3</col>' in zipfile.read('xl/drawings/drawing1.xml') # 合计左侧的浮动图片图层。
    monkeypatch.setenv('APP_ENV','development')
    assert http.get('/customer-statement-settings').status_code==403
    assert http.put('/customer-statement-settings',json=body).status_code==403
    local=preview(http,root).json()
    assert local['private_settings_available'] is False
    assert local['settings']=={} and local['stamp_image'] is None
    local_export=http.get('/translation-statements/excel',params={'project_id':str(root.id),'month':'2026-11'})
    assert local_export.status_code==200
    with ZipFile(BytesIO(local_export.content)) as zipfile:
        assert not any(name.startswith('xl/media/') for name in zipfile.namelist())
    assert not any(cell.value=='账号：001234567890' for row in load_workbook(BytesIO(local_export.content)).active for cell in row)
    monkeypatch.setenv('APP_ENV','production')
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
        assert sheet.cell(6+len(data['rows']),5).value=='CNY 30.00'
        if mode=='all':assert '汇总参考' in sheet['F6'].value
    assert preview(http,root,order_display='invalid').status_code==422
    assert http.get('/translation-statements/excel',params={'project_id':str(root.id),'month':'2026-11','order_display':'all','version':results['parents']['statement_version']}).status_code==409


def test_fixed_fee_displays_workload_and_no_unit_price_in_exports(context):
    from statement_pdf import pdf_bytes
    http, db, clients, _, _ = context
    fixed = project(db, clients[0], '010', fixed=True)
    db.add_all([
        WordCountMetric(id=uuid4(), project_id=fixed.id, dimension='company', metric_type='words', count_value=2000),
        WordCountMetric(id=uuid4(), project_id=fixed.id, dimension='company', metric_type='pages', count_value=5),
    ])
    db.commit()
    data = preview(http, fixed).json()
    row = data['rows'][0]
    assert row['pricing_mode'] == 'fixed' and row['unit_price'] is None
    assert '客户统计：字数 1,234' in row['basis']
    assert '我司统计：页数 5' in row['basis']
    assert '2,000' not in row['basis']
    assert row['subtotal'] == '500.00' and not data['pending']
    sheet = load_workbook(BytesIO(statements.excel_bytes(data))).active
    assert '单价' not in [cell.value for cell in sheet[5]]
    assert sheet['E5'].value == '固定价格' and sheet['E6'].value == 'CNY 500.00'
    assert '页数 5' in sheet['D6'].value
    assert pdf_bytes([data]).startswith(b'%PDF-')

    project(db, clients[0], '011')
    mixed = preview(http, fixed, scope='customer').json()
    sheet = load_workbook(BytesIO(statements.excel_bytes(mixed))).active
    assert sheet['E5'].value == '单价'
    assert sheet['E6'].value is None and sheet['F6'].value == 'CNY 500.00'
    assert sheet['E7'].value == 'CNY 100.000'


def test_order_display_keeps_standalone_projects_and_currency_groups(context):
    http,db,clients,_,_=context
    root=project(db,clients[0]);project(db,clients[0],'002',fixed=True,currency='USD')
    for mode in ('parents','all','children'):
        result=preview(http,root,scope='customer',order_display=mode).json()
        assert len(result['rows'])==2
        assert result['totals']=={'CNY':'123.40','USD':'500.00'}


def test_company_subject_and_conditional_customer_order_column(context,monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    http,db,clients,_,_=context
    root=project(db,clients[0])
    settings=http.get('/customer-statement-settings').json()
    assert settings['company']=='广州信实翻译服务有限公司'
    assert len(settings['company_options'])==3
    assert '客户单号' not in [cell.value for cell in load_workbook(BytesIO(statements.excel_bytes(preview(http,root).json()))).active[5]]
    response=http.put('/customer-statement-settings',json={'revision':settings['revision'],'company':statements.COMPANIES[1]})
    assert response.status_code==200,response.text
    root.customer_order_no='PO-客户-123';db.commit()
    data=preview(http,root).json()
    assert data['company']==statements.COMPANIES[1]
    assert data['rows'][0]['customer_order_no']=='PO-客户-123'
    sheet=load_workbook(BytesIO(statements.excel_bytes(data))).active
    assert sheet['A5'].value=='客户单号'
    assert sheet['A6'].value=='PO-客户-123'
    assert not any(cell.value in ('订单号','账单月份') for cell in sheet[5])
    invalid=http.put('/customer-statement-settings',json={'revision':response.json()['revision'],'company':'其他主体'})
    assert invalid.status_code==422


def test_company_table_creation_is_repeatable(environment):
    from tools.apply_statement_company_migration import apply_migration
    db,_=environment
    apply_migration(db.connection());apply_migration(db.connection())
    assert inspect(db.connection()).has_table('customer_statement_company')


def test_customer_export_omits_client_code_and_uses_three_price_decimals(context):
    http,db,clients,_,_=context
    root=project(db,clients[0])
    root.customer_charge_items[0].unit_price_excl_tax=Decimal('1.2345');db.commit()
    data=preview(http,root).json()
    sheet=load_workbook(BytesIO(statements.excel_bytes(data))).active
    assert clients[0].client_code not in str(sheet['A3'].value)
    assert sheet['E6'].value=='CNY 1.235'
    assert '(' not in sheet['E6'].value and '（' not in sheet['E6'].value
    assert Decimal(data['rows'][0]['unit_price'])==Decimal('1.2345')


def test_pdf_and_excel_keep_paper_content_titles_and_bold_styles(context,monkeypatch):
    from reportlab.platypus import SimpleDocTemplate,Paragraph
    from statement_pdf import pdf_bytes
    http,db,clients,_,_=context
    root=project(db,clients[0]);data=preview(http,root).json()
    data.update(title='2026-11 对账单',issue_date='2026-11-05',pending=['测试订单：金额待补'])
    data['rows'][0].update(origin_client_id='source',origin_client_name='原客户示例',remarks='仅给客户的说明')
    paragraphs=[];original=SimpleDocTemplate.build
    def capture(document,story,*args,**kwargs):
        def visit(item):
            if isinstance(item,Paragraph):paragraphs.append(item)
            for row in getattr(item,'_cellvalues',[]):
                for cell in row:
                    for child in cell if isinstance(cell,(tuple,list)) else [cell]:visit(child)
            for child in getattr(item,'_content',[]):visit(child)
        for item in story:visit(item)
        return original(document,story,*args,**kwargs)
    monkeypatch.setattr(SimpleDocTemplate,'build',capture)
    assert pdf_bytes([data]).startswith(b'%PDF-')
    texts=[p.getPlainText() for p in paragraphs]
    assert '对账单' in texts and '2026-11 对账单' not in texts
    for value in ('原客户示例','仅给客户的说明','待补资料：测试订单：金额待补','2026-11-05'):
        assert any(value in text for text in texts)
    assert data['rows'][0]['received_date'] in texts
    assert all('Bold' in p.style.fontName for p in paragraphs if p.style.name in ('heading','company','title','total','total_label','account'))
    sheet=load_workbook(BytesIO(statements.excel_bytes(data))).active
    assert sheet['A2'].value=='对账单' and sheet['A1'].font.sz==15 and sheet['A2'].font.sz==16.5
    assert sheet['A5'].value=='原客户' and sheet['A6'].value=='原客户示例'
    assert sheet['A3'].value=='客户：'+data['client_name'] and '账单月份：' in sheet['F3'].value
    assert sheet['B6'].value==data['rows'][0]['received_date'] and sheet.column_dimensions['B'].width>=20
    assert sheet['A5'].font.bold and sheet['A1'].font.bold
