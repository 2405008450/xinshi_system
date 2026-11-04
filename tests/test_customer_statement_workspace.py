"""对账单编排：仅在隔离内存数据库验证，不连接业务库。"""
from copy import deepcopy
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy import inspect
from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
import customer_statement_workspace as service
from tools.apply_customer_statement_workspace_migration import apply_migration,TABLES


@pytest.fixture
def setup(context):
    http,db,clients,granted,user=context
    granted.add('projects:write');http.app.include_router(service.router)
    first=project(db,clients[0],'001','2026-10');second=project(db,clients[0],'002','2026-11',fixed=True)
    return http,db,clients,granted,user,first,second


def imported(setup,months=None):
    http,_,_,_,_,first,_=setup
    response=http.post('/translation-statement-workspaces/import',json={'project_id':str(first.id),'months':months or ['2026-10','2026-11'],'revision':0,'confirmed':True})
    assert response.status_code==200,response.text
    return response.json()


def change(setup,state,action,data,mode='children',expected=200):
    http=setup[0]
    response=http.post(f"/translation-statement-workspaces/{state['client_id']}/actions",params={'mode':mode},json={'revision':state['revision'],'action':action,'data':data,'confirmed':True})
    assert response.status_code==expected,response.text
    return response.json()


def test_multimonth_import_move_uniqueness_and_original_project_untouched(setup):
    http,db,clients,_,_,first,second=setup
    state=imported(setup);assert len(state['payload']['tasks'])==2
    board1=state['documents'][0]['id']
    assert state['documents'][0]['statement']['totals']=={'CNY':'623.40'}
    state=change(setup,state,'create_board',{'name':'第二份'})
    board2=state['documents'][1]['id']
    state=change(setup,state,'move_tasks',{'task_ids':[str(first.id)],'board_id':board2,'month':'2026-12'})
    assert [len(board['statement']['rows']) for board in state['documents']]==[1,1]
    assert state['documents'][1]['statement']['month']=='2026-12'
    assert first.customer_charge_items[0].billing_month=='2026-10'
    body={'project_id':str(first.id),'months':['2026-10','2026-11'],'revision':state['revision'],'confirmed':True,'board_id':board1}
    duplicate=http.post('/translation-statement-workspaces/import',json=body).json()
    assert duplicate['imported']==0 and duplicate['existing']==2
    assert duplicate['payload']['tasks'][str(first.id)]['board_id']==board2
    state=change(setup,duplicate,'restore_task',{'task_ids':[str(first.id)]})
    assert state['payload']['tasks'][str(first.id)]['month']=='2026-10'
    assert state['payload']['tasks'][str(first.id)]['board_id']==board1


def test_edits_confirmation_audit_restore_and_immutable_identity(setup):
    http,db,_,_,user,first,_=setup
    state=imported(setup);board=state['documents'][0];line=board['statement']['rows'][0]
    target={'board_id':board['id'],'row_id':line['_row_id'],'fields':{'project_name':'对账单专用名称','subtotal':'25.50','remarks':'约定调整'}}
    no_confirm=http.post(f"/translation-statement-workspaces/{state['client_id']}/actions",json={'revision':state['revision'],'action':'edit_row','data':target})
    assert no_confirm.status_code==422
    state=change(setup,state,'edit_row',target)
    changed=state['documents'][0]['statement']['rows'][0]
    assert changed['project_name']=='对账单专用名称' and changed['order_no']==line['order_no']
    assert first.project_name=='测试项目.docx'
    assert Decimal(first.customer_charge_items[0].unit_price_excl_tax)==100
    assert state['documents'][0]['statement']['totals']=={'CNY':'525.50'}
    change(setup,state,'edit_row',{**target,'fields':{'order_no':'OTHER'}},expected=422)
    change(setup,state,'edit_row',{**target,'fields':{'subtotal':'NaN'}},expected=422)
    stale={**state,'revision':1};change(setup,stale,'edit_row',target,expected=409)
    history=http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()
    assert history['items'][0]['actor_name']==user.full_name
    assert history['items'][0]['created_at'].endswith('+08:00')
    assert history['items'][0]['changes']['fields']['project_name']['before']=='测试项目.docx'
    state=change(setup,state,'restore_history',{'history_id':history['items'][0]['id']})
    assert state['documents'][0]['statement']['rows'][0]['project_name']=='测试项目.docx'
    assert http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()['total']==3


def test_header_layout_excel_multisheet_and_formula_escape(setup):
    http,db,_,_,_,first,_=setup
    state=imported(setup);first_board=state['documents'][0]['id']
    state=change(setup,state,'edit_board',{'board_id':first_board,'fields':{'company':'=1+1','title':'合并月结对账单','bank_name':'编排开户行','billing_label':'十月至十一月'}})
    state=change(setup,state,'position_board',{'board_id':first_board,'x':150,'y':35})
    assert state['documents'][0]['x']==150
    state=change(setup,state,'create_board',{'name':'另一份'})
    second_board=state['documents'][1]['id']
    state=change(setup,state,'move_tasks',{'task_ids':[str(first.id)],'board_id':second_board,'month':'2026-12'})
    response=http.get(f"/translation-statement-workspaces/{state['client_id']}/excel",params=[('revision',state['revision']),('board_ids',first_board),('board_ids',second_board)])
    assert response.status_code==200,response.text
    workbook=load_workbook(BytesIO(response.content));assert len(workbook.worksheets)==2
    sheet=workbook.worksheets[0]
    assert sheet['A1'].data_type!='f'
    assert sheet['A2'].value=='合并月结对账单'
    assert sheet['A5'].value=='订单号'
    assert sheet['B5'].value=='账单月份'
    assert sheet['B6'].value=='2026-11'
    assert sheet['A6'].value==state['documents'][0]['statement']['rows'][0]['order_no']
    assert any(cell.value=='开户行：编排开户行' for row in sheet for cell in row)
    assert http.get(f"/translation-statement-workspaces/{state['client_id']}/excel",params={'revision':1,'board_ids':first_board}).status_code==409


def test_no_cross_customer_restore_and_permissions(setup):
    http,_,clients,granted,_,first,_=setup
    state=imported(setup)
    other=project(setup[1],clients[1],'003')
    new=http.post('/translation-statement-workspaces/import',json={'project_id':str(other.id),'months':['2026-11'],'revision':0,'confirmed':True}).json()
    history=http.get(f"/translation-statement-workspaces/{new['client_id']}/history").json()
    change(setup,state,'restore_history',{'history_id':history['items'][0]['id']},expected=422)
    change(setup,state,'move_tasks',{'task_ids':[str(other.id)],'board_id':state['documents'][0]['id'],'month':'2026-12'},expected=422)
    granted.remove('projects:write')
    change(setup,state,'create_board',{'name':'越权'},expected=403)
    granted.remove('projects:read')
    assert http.get(f'/translation-statement-workspaces/project/{first.id}').status_code==403


def test_create_only_migration_repeatable(setup):
    _,db,*_=setup
    for name in reversed(TABLES):service.Base.metadata.tables[name].drop(db.connection())
    before=set(inspect(db.connection()).get_table_names())
    existing=[item['name'] for item in inspect(db.connection()).get_columns('translation_sub_order_charge_item')]
    apply_migration(db.connection());apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names())-before==set(TABLES)
    assert existing==[item['name'] for item in inspect(db.connection()).get_columns('translation_sub_order_charge_item')]
