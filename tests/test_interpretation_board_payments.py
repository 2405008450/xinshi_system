"""合并/特殊结算按单据实际金额核对付款，使用隔离内存数据库。"""
from copy import deepcopy
from uuid import UUID
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_interpretation_settlement_settings import seed
import interpretation_customer_finance as finance
import interpretation_statement_workspace as workspace
import interpretation_board_payments as payments


def generate(db,actor,project,mode='sub_client'):
    current=workspace.read(project.id,mode,['2026-11'],db,actor)
    result=workspace.write(project.id,workspace.Write(revision=current['revision'],mode=mode,action='generate',months=['2026-11'],period_number=1 if mode!='special' else None,project_ids=[project.id]),db,actor)
    return result,next(row for row in result['documents'] if row['status']=='active')


def test_board_actual_amount_payment_confirm_history_and_ledger(environment,monkeypatch):
    db,actor,client,children,projects=seed(environment,monkeypatch)
    monkeypatch.setattr('hr_access.can_manage_hr',lambda _db,user:user.id==actor.id)
    result,board=generate(db,actor,projects[0])
    result=workspace.write(projects[0].id,workspace.Write(revision=result['revision'],mode='sub_client',action='edit_row',board_id=board['id'],data={'row_id':board['statement']['rows'][0]['line_id'],'fields':{'subtotal':'125'}}),db,actor)
    current=payments.read(projects[0].id,board['id'],'sub_client',db,actor)
    assert current['totals']=={'CNY':'125.00'}
    data=payments.Write(revision=current['revision'],registration={'confirmation':{'is_paid':True,'payment_option':'deposit'},'payments':[{'stage_type':'deposit','actual_amount':50},{'stage_type':'final','actual_amount':75}]})
    saved=payments.save(projects[0].id,board['id'],data,'sub_client',db,actor)
    assert saved['registration']['confirmation']['full_match_status']=='matched'
    with pytest.raises(HTTPException) as stale:payments.save(projects[0].id,board['id'],data,'sub_client',db,actor)
    assert stale.value.status_code==409
    payment_id=UUID(saved['registration']['payments'][0]['id'])
    confirmed=payments.confirm(projects[0].id,board['id'],payments.PaymentConfirm(revision=saved['revision'],payment_id=payment_id),'sub_client',db,actor)
    assert confirmed['registration']['payments'][0]['confirmed_at'].endswith('+08:00')
    with pytest.raises(HTTPException) as denied:payments.confirm(projects[0].id,board['id'],payments.PaymentConfirm(revision=confirmed['revision'],payment_id=payment_id),'sub_client',db,environment[1][1])
    assert denied.value.status_code==403
    assert payments.history(projects[0].id,board['id'],'sub_client',1,db,actor)['total']==2
    units,covered=payments.ledger_units(db,[finance.context(db,'project',projects[0].id)])
    assert units[0]['billing_totals']=={'CNY':'125.00'} and units[0]['received_totals']=={'CNY':'125.00'}
    assert units[0]['paid_full'] and units[0]['payment_difference']=={'CNY':'0.00'}
    assert covered==[str(projects[0].id)]
    assert finance.context(db,'project',projects[0].id)['received_totals']=={}
    with pytest.raises(HTTPException) as blocked:generate(db,actor,projects[0])
    assert blocked.value.status_code==409
    db.rollback()
    # 下一期不复制已登记款项。
    result=workspace.write(projects[0].id,workspace.Write(revision=confirmed['revision'],mode='sub_client',action='new_board',board_id=board['id']),db,actor)
    new=next(row for row in result['documents'] if row['id']!=board['id'])
    assert not payments.read(projects[0].id,new['id'],'sub_client',db,actor)['registration']['confirmation']['is_paid']


def test_special_board_independence_mismatch_clear_and_stale_edit(environment,monkeypatch):
    db,actor,client,children,projects=seed(environment,monkeypatch);project=projects[4]
    result,first=generate(db,actor,project,'special')
    current=payments.read(project.id,first['id'],'special',db,actor)
    bad=payments.Write(revision=current['revision'],registration={'confirmation':{'is_paid':True,'payment_option':'full','full_payment_amount':80}})
    with pytest.raises(HTTPException) as mismatch:payments.save(project.id,first['id'],bad,'special',db,actor)
    assert mismatch.value.status_code==422
    bad.registration.confirmation.mismatch_reason='约定减免'
    saved=payments.save(project.id,first['id'],bad,'special',db,actor)
    generated=workspace.write(project.id,workspace.Write(revision=saved['revision'],mode='special',action='generate',months=['2026-11'],project_ids=[project.id]),db,actor)
    second=next(row for row in generated['documents'] if row['id']!=first['id'])
    assert not payments.read(project.id,second['id'],'special',db,actor)['registration']['confirmation']['is_paid']
    units,_=payments.ledger_units(db,[finance.context(db,'project',project.id)])
    assert len(units)==2 and sorted(row['received_totals'].get('CNY','0.00') for row in units)==['0.00','80.00']
    cleared=payments.save(project.id,first['id'],payments.Write(revision=generated['revision'],registration={'confirmation':{'is_paid':False}}),'special',db,actor)
    assert not cleared['registration']['confirmation']['is_paid']
    assert payments.history(project.id,first['id'],'special',1,db,actor)['total']==2
