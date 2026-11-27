"""口译按实际对账单登记合并/特殊结算付款；不覆盖原项目历史付款。"""
from copy import deepcopy
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field
from uuid import UUID
from database import get_db
from routers.auth import get_current_user
from business_finance_payment import Registration,registration,history_snapshot
from interpretation_payment_registration import prepare,PaymentConfirm,mark_confirmed
import interpretation_customer_finance as finance
import interpretation_statement_workspace as workspace
from business_finance_source import MODULE,select_module

router=APIRouter(prefix='/statement-payments',dependencies=[Depends(select_module)])


def board_context(db,target,board_id,mode,lock=False):
    if MODULE.get()!='interpretation':raise HTTPException(422,'此付款入口仅用于口译')
    project,client,storage,payload,ws,group,mode=workspace.context(db,target,mode,lock)
    board=next((row for row in ws['boards'] if row['id']==board_id and row['group']==group),None)
    if not board or board['status']!='active':raise HTTPException(404,'有效对账单不存在')
    return client,storage,payload,ws,group,board


def initial(db,board,ws):
    if board.get('payment_registration') is not None:return deepcopy(board['payment_registration'])
    ids={line['root_id'] for line in board['statement']['rows'] if line.get('counted_in_total',True)}
    shared={key for key in ids if sum(any(line['root_id']==key for line in other['statement']['rows']) for other in ws['boards'] if other['status']=='active')>1}
    payments=[]
    for key in sorted(ids-shared):
        row=finance.record(db,'project',UUID(key))
        for value in finance.settlement(row.payload if row else {}).payments:payments.append(value.model_dump(mode='json'))
    return registration({'settlement':{'payment_status':'partial' if payments else 'unrecorded','payments':payments}})


def result(db,ws,board):
    return dict(revision=ws['revision'],totals=workspace.rendered(board)['statement']['totals'],registration=initial(db,board,ws),
        notice='项目旧付款只带入核对，保存后按本对账单登记；同一项目分属多份特殊单据时，请分别核对付款，原项目记录仍保留。')


@router.get('/{target}/{board_id}')
def read(target:UUID,board_id:str,mode:workspace.Mode='monthly',db=Depends(get_db),user=Depends(get_current_user)):
    finance.permission(db,user,'project')
    *_,ws,group,board=board_context(db,target,board_id,mode)
    return result(db,ws,board)


class Write(BaseModel):
    revision:int=Field(ge=0)
    registration:Registration


@router.put('/{target}/{board_id}')
def save(target:UUID,board_id:str,data:Write,mode:workspace.Mode='monthly',db=Depends(get_db),user=Depends(get_current_user)):
    finance.permission(db,user,'project',True)
    client,storage,payload,ws,group,board=board_context(db,target,board_id,mode,True)
    if ws['revision']!=data.revision:raise HTTPException(409,'对账单或付款已修改，请重新读取后保存')
    before=deepcopy(ws)
    value={'settlement':{},'payment_registration':data.registration.model_dump(mode='json')}
    prepare(value,{'payment_registration':initial(db,board,ws)},workspace.rendered(board)['statement']['totals'])
    board['payment_registration']=value['payment_registration']
    if board['payment_registration']['confirmation'].get('full_reference_amount') is not None:
        board['payment_registration']['confirmation']['full_reference_label']='对账单总价'
    workspace.store(db,user,client,storage,payload,ws,group,'保存对账单付款',before)
    return result(db,ws,board)


@router.post('/{target}/{board_id}/confirm')
def confirm(target:UUID,board_id:str,data:PaymentConfirm,mode:workspace.Mode='monthly',db=Depends(get_db),user=Depends(get_current_user)):
    finance.permission(db,user,'project',True)
    from hr_access import can_manage_hr
    if not can_manage_hr(db,user):raise HTTPException(403,'仅行政部人员可确认付款')
    client,storage,payload,ws,group,board=board_context(db,target,board_id,mode,True)
    if ws['revision']!=data.revision:raise HTTPException(409,'付款或对账单已修改，请重新读取')
    before=deepcopy(ws);value=initial(db,board,ws)
    mark_confirmed(value,user,data.payment_id);board['payment_registration']=value
    workspace.store(db,user,client,storage,payload,ws,group,'确认对账单付款',before)
    return result(db,ws,board)


@router.get('/{target}/{board_id}/history')
def history(target:UUID,board_id:str,mode:workspace.Mode='monthly',page:int=Query(1,ge=1),db=Depends(get_db),user=Depends(get_current_user)):
    finance.permission(db,user,'project')
    _,storage,_,_,_,_=board_context(db,target,board_id,mode)
    if not storage:return dict(items=[],total=0)
    events=db.query(finance.InterpretationCustomerFinanceHistory).filter_by(finance_id=storage.id).order_by(finance.InterpretationCustomerFinanceHistory.revision.desc()).all()
    def snapshot(value):
        board=next((row for row in value.get('_oral_workspace',{}).get('boards',[]) if row['id']==board_id),{})
        return history_snapshot({'payment_registration':board.get('payment_registration')})
    from annotation_progress_time import business_datetime
    rows=[]
    for event in events:
        old,new=snapshot(event.before),snapshot(event.after)
        if old!=new:rows.append(dict(id=event.id,actor_name=event.actor_name,created_at=business_datetime(event.created_at).isoformat(),before=old,after=new))
    return dict(items=rows[(page-1)*10:page*10],total=len(rows))


def ledger_units(db,items):
    """有独立单据的项目按有效单据统计，避免再累加源项目金额及旧付款。"""
    mapping={row['id']:row for row in items};units=[];covered=set()
    client_ids={UUID(row['client_id']) for row in items if row.get('client_id')}
    storage=db.query(finance.InterpretationCustomerFinance).filter(finance.InterpretationCustomerFinance.client_id.in_(client_ids)).all() if client_ids else []
    for saved in storage:
        ws=(saved.payload or {}).get('_oral_workspace',{})
        for board in ws.get('boards',[]):
            if board['status']!='active' or not board['group'].startswith('interpretation:') or board.get('mode')=='individual':continue
            roots={row['root_id'] for row in board['statement']['rows']}
            selected=[mapping[key] for key in roots if key in mapping]
            if not selected:continue
            # 对账单是不可拆分的结算单位；混合负责人时仍统计完整单据金额。
            billing=workspace.rendered(board)['statement']['totals'];state=initial(db,board,ws)
            confirmation=state['confirmation'];received={}
            if confirmation.get('is_paid') and confirmation.get('payment_option')=='full':
                if confirmation.get('full_payment_amount') is not None:received[confirmation.get('full_payment_currency','CNY')]=Decimal(str(confirmation['full_payment_amount']))
            else:
                for payment in state['payments']:
                    if payment.get('actual_amount') is not None:
                        code=payment.get('currency','CNY');received[code]=received.get(code,Decimal(0))+Decimal(str(payment['actual_amount']))
            full=confirmation.get('is_paid') and (confirmation.get('payment_option')=='full' or any(row.get('stage_type')=='final' for row in state['payments']))
            difference={key:format(received.get(key,Decimal(0))-Decimal(str(billing.get(key,0))),'.2f') for key in billing.keys()|received.keys()}
            units.append(dict(id=board['id'],client_id=str(saved.client_id),client_name=selected[0].get('client_name'),name=board['number']+' · '+board['name'],mode=board['mode'],months=board['months'],project_ids=sorted(roots),billing_totals=billing,received_totals={key:format(value,'.2f') for key,value in received.items()},payment_difference=difference,paid_full=bool(full),partial_scope=len(selected)!=len(roots)))
            covered.update(roots)
    return units,sorted(covered)
