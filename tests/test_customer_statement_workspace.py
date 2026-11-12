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


def test_local_workspace_excludes_private_fields_from_documents_and_history(setup,monkeypatch):
    http=setup[0]
    monkeypatch.setenv('APP_ENV','production')
    state=imported(setup)
    board=state['documents'][0]
    state=change(setup,state,'edit_board',{'board_id':board['id'],'fields':{'account_number':'TEST-OA-ACCOUNT'}})
    assert state['documents'][0]['statement']['settings']['account_number']=='TEST-OA-ACCOUNT'
    path=f"/translation-statement-workspaces/{state['client_id']}"

    monkeypatch.setenv('APP_ENV','development')
    local=http.get(path)
    assert local.status_code==200 and 'TEST-OA-ACCOUNT' not in local.text
    assert local.json()['documents'][0]['statement']['stamp_image'] is None
    log=http.get(f'{path}/history')
    assert 'TEST-OA-ACCOUNT' not in log.text
    record_id=log.json()['items'][0]['id']
    assert 'TEST-OA-ACCOUNT' not in http.get(f'{path}/history/{record_id}').text
    change(setup,state,'edit_board',{'board_id':board['id'],'fields':{'account_number':'TEST-LOCAL-ACCOUNT'}},expected=403)
    change(setup,state,'restore_history',{'history_id':record_id})

    monkeypatch.setenv('APP_ENV','production')
    assert http.get(path).json()['documents'][0]['statement']['settings']['account_number']=='TEST-OA-ACCOUNT'


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


def test_header_layout_excel_multisheet_and_formula_escape(setup,monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
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
    assert sheet['A5'].value=='来稿日期'
    assert sheet['B5'].value=='项目名称'
    assert sheet['B6'].value==state['documents'][0]['statement']['rows'][0]['project_name']
    assert not any(cell.value in ('订单号','账单月份') for cell in sheet[5])
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


def test_delete_selected_boards_releases_tasks_for_regeneration_and_keeps_history(setup):
    http,db,_,_,user,first,second=setup
    state=imported(setup);original=state['documents'][0]['id']
    state=change(setup,state,'create_board',{'name':'保留的一份'})
    keep=state['documents'][1]['id']
    state=change(setup,state,'move_tasks',{'task_ids':[str(second.id)],'board_id':keep,'month':'2026-11'})
    state=change(setup,state,'edit_row',{'board_id':original,'row_id':state['documents'][0]['statement']['rows'][0]['_row_id'],'fields':{'project_name':'删除前自定义名称'}})
    stale=deepcopy(state)
    state=change(setup,state,'delete_boards',{'board_ids':[original]})
    assert [board['id'] for board in state['documents']]==[keep]
    assert str(first.id) not in state['payload']['tasks'] and str(second.id) in state['payload']['tasks']
    assert first.project_name=='测试项目.docx'
    log=http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()['items'][0]
    assert log['action']=='删除对账单' and log['actor_name']==user.full_name and log['restorable']
    assert log['changes']['deleted_boards'][0]['name']
    stored=db.get(service.StatementWorkspaceHistory, __import__('uuid').UUID(log['id']))
    assert stored.before['tasks'][str(first.id)]['rows'][0]['project_name']=='删除前自定义名称'
    change(setup,stale,'delete_boards',{'board_ids':[keep]},expected=409)
    restored=change(setup,state,'restore_history',{'history_id':log['id']})
    assert restored['documents'][0]['statement']['rows'][0]['project_name']=='删除前自定义名称'
    state=change(setup,restored,'delete_boards',{'board_ids':[original]})
    response=http.post('/translation-statement-workspaces/import',json={'project_id':str(first.id),'months':['2026-10','2026-11'],'revision':state['revision'],'board_id':keep,'confirmed':True})
    assert response.status_code==200,response.text
    regenerated=response.json();assert regenerated['imported']==1 and regenerated['existing']==1
    assert len(regenerated['payload']['tasks'])==2
    assert regenerated['payload']['tasks'][str(first.id)]['rows'][0]['project_name']=='测试项目.docx'
    assert any(row['action']=='删除对账单' for row in http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()['items'])


def test_delete_all_batch_validation_restore_and_regenerate(setup):
    http,_,clients,granted,_,first,_=setup
    state=imported(setup);state=change(setup,state,'create_board',{'name':'空对账单'})
    ids=[board['id'] for board in state['documents']]
    for data in [{'board_ids':ids},{'board_ids':[]},{'board_ids':[ids[0],ids[0]],'confirmation':'删除'},{'board_ids':[ids[0],str(uuid4())],'confirmation':'删除'}]:
        response=http.post(f"/translation-statement-workspaces/{state['client_id']}/actions",json={'revision':state['revision'],'action':'delete_boards','data':data,'confirmed':True})
        assert response.status_code in (404,422)
    unchanged=http.get(f"/translation-statement-workspaces/{state['client_id']}").json();assert unchanged['revision']==state['revision']
    deleted=change(setup,state,'delete_boards',{'board_ids':ids,'confirmation':'删除'})
    assert deleted['documents']==[] and deleted['payload']['tasks']=={} and deleted['payload']['roots']=={}
    change(setup,deleted,'create_board',{'name':'应提示先生成'},expected=422)
    response=http.post('/translation-statement-workspaces/import',json={'project_id':str(first.id),'months':['2026-10','2026-11'],'revision':deleted['revision'],'confirmed':True})
    assert response.status_code==200,response.text
    regenerated=response.json();assert len(regenerated['documents'])==1 and regenerated['imported']==2
    assert regenerated['documents'][0]['id'] not in ids
    log=http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()['items'][0]
    # 重新生成也可恢复到生成前的空工作区。
    assert log['restorable']
    empty=change(setup,regenerated,'restore_history',{'history_id':log['id']})
    assert not empty['documents']
    granted.remove('projects:write')
    change(setup,empty,'delete_boards',{'board_ids':ids,'confirmation':'删除'},expected=403)


def test_inline_document_edit_audits_every_field_and_moves_month_without_changing_project(setup,monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    http,db,_,_,user,first,_=setup
    state=imported(setup);board=state['documents'][0];line=board['statement']['rows'][0]
    state=change(setup,state,'edit_document',{'board_id':board['id'],'fields':{'company':'对账单抬头','title':'核对清单','bank_name':'对账单专用银行'},'rows':[{'row_id':line['_row_id'],'fields':{'project_name':'对账专用名称','subtotal':'42.50','remarks':'协商调整','billing_month':'2026-12'}}]})
    changed=state['documents'][0]['statement'];row=next(item for item in changed['rows'] if item['_row_id']==line['_row_id'])
    assert changed['company']=='对账单抬头' and changed['title']=='核对清单' and changed['settings']['bank_name']=='对账单专用银行'
    assert row['project_name']=='对账专用名称' and row['subtotal']=='42.50' and row['billing_month']=='2026-12'
    assert first.project_name=='测试项目.docx' and first.customer_charge_items[0].billing_month=='2026-10'
    assert first.customer_charge_items[0].unit_price_excl_tax==100
    log=http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()['items'][0]
    assert log['action']=='直接编辑对账单' and log['actor_name']==user.full_name and log['created_at'].endswith('+08:00')
    assert log['changes']['fields']['company']['after']=='对账单抬头'
    assert log['changes']['rows'][0]['fields']['project_name']=={'before':line['project_name'],'after':'对账专用名称'}
    assert log['changes']['rows'][0]['fields']['billing_month']['after']=='2026-12'
    restored=change(setup,state,'restore_history',{'history_id':log['id']})
    assert restored['documents'][0]['statement']['rows'][0]['project_name']==line['project_name']
    assert restored['documents'][0]['statement']['company']==board['statement']['company']


def test_inline_invalid_changes_are_atomic_and_identity_locked(setup):
    http,_,_,_,_,_,_=setup;state=imported(setup);board=state['documents'][0];line=board['statement']['rows'][0]
    for fields in [{'order_no':'FAKE'},{'billing_month':'2026-13'},{'subtotal':'NaN'},{'currency':'bad-code'}]:
        change(setup,state,'edit_document',{'board_id':board['id'],'fields':{'company':'不可部分保存'},'rows':[{'row_id':line['_row_id'],'fields':fields}]},expected=422)
    current=http.get(f"/translation-statement-workspaces/{state['client_id']}").json()
    assert current['revision']==state['revision'] and current['documents'][0]['statement']['company']==board['statement']['company']
    change(setup,state,'edit_document',{'board_id':board['id'],'rows':[{'row_id':'missing','fields':{'remarks':'wrong'}}]},expected=409)
    state=change(setup,state,'edit_document',{'board_id':board['id'],'rows':[{'row_id':line['_row_id'],'fields':{'remarks':'修改一次'}}]})
    change(setup,{**state,'revision':state['revision']-1},'edit_document',{'board_id':board['id'],'rows':[{'row_id':line['_row_id'],'fields':{'remarks':'旧窗口覆盖'}}]},expected=409)


def test_membership_tracks_board_months_delete_restore_and_customer_snapshot(setup):
    import crud
    from translation_statement_status import attach
    http,db,clients,_,_,first,second=setup
    attach(db,[first,second]);assert first.statement_status==[]
    state=imported(setup);board=state['documents'][0]['id']
    root=crud.get_translation_project(db,first.id)
    assert root.statement_status==[{'client_id':str(clients[0].id),'board_id':board,'board_name':'2026-10、2026-11 对账单','months':['2026-10']}]
    state=change(setup,state,'create_board',{'name':'另一个月'})
    other=state['documents'][1]['id']
    state=change(setup,state,'move_tasks',{'task_ids':[str(first.id)],'board_id':other,'month':'2027-01'})
    assert crud.get_translation_project(db,first.id).statement_status[0]['months']==['2027-01']
    assert crud.get_translation_project(db,first.id).statement_status[0]['board_id']==other
    # 项目客户改动不应掩盖已独立保存的旧客户对账单归属。
    first.client_id=clients[1].id;db.commit()
    assert crud.get_translation_project(db,first.id).statement_status[0]['client_id']==str(clients[0].id)
    state=change(setup,state,'delete_boards',{'board_ids':[other]})
    assert crud.get_translation_project(db,first.id).statement_status==[]
    assert crud.get_translation_project(db,second.id).statement_status
    log=http.get(f"/translation-statement-workspaces/{state['client_id']}/history").json()['items'][0]
    state=change(setup,state,'restore_history',{'history_id':log['id']})
    assert crud.get_translation_project(db,first.id).statement_status[0]['months']==['2027-01']


def test_issue_date_is_frozen_and_month_moves_to_title(setup,monkeypatch):
    from datetime import datetime,timezone,timedelta
    import customer_statement_workspace as service
    import customer_statements as statements
    http,db,clients,*_=setup
    first=datetime(2026,11,5,18,tzinfo=timezone(timedelta(hours=8)))
    monkeypatch.setattr(service,'business_now',lambda:first)
    state=imported(setup,['2026-10'])
    board=state['documents'][0]
    assert board['fields']['issue_date']=='2026-11-05'
    monkeypatch.setattr(service,'business_now',lambda:datetime(2026,11,8,18,tzinfo=first.tzinfo))
    fresh=http.get(f"/translation-statement-workspaces/{clients[0].id}").json()
    paper=fresh['documents'][0]['statement']
    assert paper['issue_date']=='2026-11-05'
    assert statements.statement_title(paper)=='对账单'
    # 旧版本从首次生成记录推算日期，不能把再次查看的日期当作出账日。
    row=db.get(service.StatementWorkspace,clients[0].id)
    import copy
    original=copy.deepcopy(row.payload)
    row.payload=copy.deepcopy(original)
    for saved in row.payload['boards']:saved['fields'].pop('issue_date',None)
    assert service.serialize(row,db=db)['documents'][0]['statement']['issue_date']=='2026-11-05'
    row.payload=original


def test_pdf_download_checks_revision_and_board_scope(setup):
    http,db,clients,_,_,_,_=setup
    state=imported(setup);board=state['documents'][0]
    params={'revision':state['revision'],'board_ids':[board['id']]}
    response=http.get(f"/translation-statement-workspaces/{state['client_id']}/pdf",params=params)
    assert response.status_code==200,response.text
    assert response.headers['content-type']=='application/pdf'
    assert response.content.startswith(b'%PDF-') and len(response.content)>1000
    assert http.get(f"/translation-statement-workspaces/{state['client_id']}/pdf",params={**params,'revision':0}).status_code==409
    assert http.get(f"/translation-statement-workspaces/{state['client_id']}/pdf",params={**params,'board_ids':['unknown']}).status_code==404
