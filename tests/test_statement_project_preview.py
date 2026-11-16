from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.test_customer_statement_workspace import setup,imported,change
from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
from statement_project_preview import build
import translation_customer_finance as finance


def test_same_file_directions_group_by_unit_price_and_keep_original_tasks(setup):
    from datetime import datetime
    from decimal import Decimal
    from io import BytesIO
    from models import TranslationSubOrder, TranslationSubOrderChargeItem
    from openpyxl import load_workbook
    from word_count_models import WordCountMetric
    from customer_statements import statement_amount

    http,db,clients,_,_,root,_=setup
    month='2026-10'
    directions=['英语→简中','日语→简中','韩语→简中']
    root.language_pair='；'.join(directions)
    children=[]
    for index, (direction,price) in enumerate(zip(directions, (100,100,200)), 1):
        child=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,
            sub_order_no=f'{root.order_no}.{index:03}',sub_project_name=root.source_file_name,
            language_pair=direction,network_file_path='同上一级订单')
        child.customer_charge_items=[TranslationSubOrderChargeItem(id=uuid4(),sequence_no=1,
            item_name='翻译费',pricing_mode='metric',currency='CNY',metric_type='words',unit_size=1000,
            unit_price_excl_tax=price,billing_month=month,created_at=datetime(2026,10,1))]
        db.add(child)
        db.add(WordCountMetric(id=uuid4(),sub_order_id=child.id,dimension='customer',
                               metric_type='words',count_value=1000*index))
        children.append(child)
    db.commit()
    order_ids=[child.id for child in children]

    preview=build(db,clients[0].id,month,order_ids)
    parent,first,last=preview['rows']
    assert parent['project_name']==root.source_file_name
    assert parent['counted_in_total'] is False
    assert parent['quantity']=='1234'
    assert parent['basis']=='客户统计 · 字数'
    assert statement_amount(parent)=='CNY 900.00（不计入合计）'
    assert first['language_pair']=='；'.join(directions[:2])
    assert first['direction_count']==2
    assert Decimal(first['subtotal'])==300
    assert statement_amount(first)=='CNY 300.00（2 个方向合计）'
    assert last['language_pair']==directions[2]
    assert Decimal(last['subtotal'])==600
    assert all(row['project_name']=='' and row['quantity'] is None and row['basis']=='' for row in (first,last))
    assert preview['totals']=={'CNY':'900.00'}

    response=http.post('/translation-statement-workspaces/import',json={
        'client_id':str(clients[0].id),'months':[month],'order_ids':list(map(str,order_ids)),
        'revision':0,'confirmed':True,
    })
    assert response.status_code==200,response.text
    workspace=response.json()
    assert set(workspace['payload']['tasks'])==set(map(str,order_ids))
    document=workspace['documents'][0]['statement']
    assert document['totals']==preview['totals']
    assert document['rows'][1]['task_ids']==list(map(str,order_ids[:2]))
    excel=http.get(f"/translation-statement-workspaces/{workspace['client_id']}/excel",
        params={'revision':workspace['revision'],'board_ids':workspace['documents'][0]['id']})
    assert excel.status_code==200,excel.text
    sheet=load_workbook(BytesIO(excel.content)).active
    assert all(cells in sheet.merged_cells for cells in ('A6:A8','B6:B8','D6:D8'))
    assert all(sheet[cell].alignment.vertical=='center' for cell in ('A6','B6','D6'))
    assert sheet['B6'].value==root.source_file_name
    assert sheet['D6'].value=='1234\n客户统计 · 字数'
    assert sheet['F6'].value=='CNY 900.00（不计入合计）'
    assert sheet['B7'].value in (None,'') and sheet['D7'].value in (None,'')
    assert '每1000计价' in sheet['E7'].value
    assert sheet['F7'].value=='CNY 300.00（2 个方向合计）'
    pdf=http.get(f"/translation-statement-workspaces/{workspace['client_id']}/pdf",
        params={'revision':workspace['revision'],'board_ids':workspace['documents'][0]['id']})
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF'),pdf.status_code

def test_preview_matches_selected_generation_and_is_read_only(setup):
    http,db,clients,_,actor,root,_=setup
    http.app.include_router(finance.router)
    other=project(db,clients[0],'003','2026-10',fixed=True)
    before=db.query(__import__('customer_statement_workspace').StatementWorkspace).count()
    data=http.post('/translation-customer-finance/statement-preview',json={'client_id':str(clients[0].id),'month':'2026-10','order_ids':[str(root.id)]})
    assert data.status_code==200,data.text
    assert data.json()['statement_number'] is None
    assert {row['root_id'] for row in data.json()['rows']}=={str(root.id)}
    assert db.query(__import__('customer_statement_workspace').StatementWorkspace).count()==before
    generated=http.post('/translation-statement-workspaces/import',json={'client_id':str(clients[0].id),'months':['2026-10'],'order_ids':[str(root.id)],'revision':0,'confirmed':True})
    assert generated.status_code==200,generated.text
    assert set(generated.json()['payload']['tasks'])=={str(root.id)}
    assert generated.json()['documents'][0]['statement']['totals']==data.json()['totals']
    numbered=http.post('/translation-customer-finance/statement-preview',json={
        'client_id':str(clients[0].id),'month':'2026-10','order_ids':[str(root.id)],
    })
    assert numbered.status_code==200,numbered.text
    assert numbered.json()['statement_number']==generated.json()['documents'][0]['statement']['statement_number']
    with pytest.raises(HTTPException):build(db,clients[1].id,'2026-10',[root.id])
    with pytest.raises(HTTPException):build(db,clients[0].id,'2026-10',[uuid4()])

def test_parent_and_child_selection_does_not_duplicate_tasks(context):
    from tests.test_customer_translation_rates import context as tree
    http,db,clients,_,actor=context
    client,root,middle,leaf=tree(db,actor)
    month=finance.order_billing_month(root.order_no)
    parent=build(db,client.id,month,[root.id])
    selected=build(db,client.id,month,[root.id,middle.id,leaf.id])
    assert len(selected['rows'])==len(parent['rows'])
    assert selected['totals']==parent['totals']

def test_pending_only_month_can_preview_and_generate_without_native_projects(setup):
    http,db,clients,_,actor,root,_=setup
    http.app.include_router(finance.router)
    state=imported(setup,['2026-10'])
    state=change(setup,state,'schedule_tasks',{'task_ids':[str(root.id)],'month':'2026-12'})
    preview=http.post('/translation-customer-finance/statement-preview',json={'client_id':str(clients[0].id),'month':'2026-12','months':['2026-11','2026-12'],'order_ids':[]})
    assert preview.status_code==200,preview.text
    assert {row['task_id'] for row in preview.json()['rows']}=={str(root.id)}
    assert preview.json()['rows'][0]['billing_month']=='2026-12'
    result=http.post('/translation-statement-workspaces/import',json={'client_id':str(clients[0].id),'months':['2026-12'],'order_ids':[],'revision':state['revision'],'confirmed':True})
    assert result.status_code==200,result.text
    assert result.json()['accepted_pending_count']==1
    assert not result.json()['pending_tasks']
