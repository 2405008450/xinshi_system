"""客户工作区内的有效账单唯一性；仅修改传入快照，不进行数据库操作。"""
from fastapi import HTTPException


def months(payload, board):
    values={task['month'] for task in payload.get('tasks',{}).values() if task.get('board_id')==board['id'] and not task.get('pending')}
    if not values or number(board):values.update(board.get('billing_months',[]))
    if board.get('period_month'):values.add(board['period_month'])
    if board.get('status_period_month'):values.add(board['status_period_month'])
    return sorted(values)


def activate(payload, board):
    board['status']='active'
    board['activation_order']=max((item.get('activation_order',0) for item in payload['boards']),default=0)+1


def number(board):
    return board.get('period_number') or board.get('status_period_number')


def peers(payload, board):
    return [item for item in payload['boards'] if item['id']!=board['id'] and
            item.get('status','active')=='active' and
            item.get('sub_client_id')==board.get('sub_client_id') and
            (item.get('settlement_scope') or 'standard')==(board.get('settlement_scope') or 'standard') and
            set(months(payload,item)) & set(months(payload,board))]


def set_period(payload, board, value):
    if board.get('settlement_scope')=='special':raise HTTPException(422,'特殊结算单不区分账期')
    if isinstance(value,bool) or not isinstance(value,int) or value<1:
        raise HTTPException(422,'账期必须为大于零的整数')
    if board.get('status','active')=='active' and any(number(item)==value for item in peers(payload,board)):
        raise HTTPException(422,f'同月份第 {value} 期已有有效对账单，请选择其他账期，或先将原对账单废除')
    billing_months=months(payload,board)
    if not billing_months:raise HTTPException(422,'请先确定对账单月份')
    board.update(period_number=value,period_month=billing_months[0] if len(billing_months)==1 else None,billing_months=billing_months)
    board.pop('status_period_number',None)
    board.pop('status_period_month',None)


def next_period(payload, template):
    if template.get('status')=='void':raise HTTPException(422,'请从有效对账单新增账期')
    # 未分期的原单保留全部项目，作为第一期；废除版本不占用账期。
    if not number(template):set_period(payload,template,1)
    return max([number(template),*[number(item) or 0 for item in peers(payload,template)]])+1


def normalize(payload):
    occupied=set();changes=[]
    ordered=sorted(enumerate(payload['boards']),key=lambda pair:(pair[1].get('activation_order',0),pair[0]),reverse=True)
    for _,board in ordered:
        status=board.get('status','active')
        if status not in ('active','void'):raise HTTPException(422,'请选择有效或废除状态')
        keys={(board.get('sub_client_id'),board.get('settlement_scope') or 'standard',month,board.get('period_number') or board.get('status_period_number')) for month in months(payload,board)}
        if board.get('settlement_scope')=='special':keys=set()
        if status=='active' and keys & occupied:
            status='void'
            changes.append({'board_id':board['id'],'name':board.get('name',board['id']),'before':'active','after':'void','reason':'同月份同账期已有有效对账单'})
        board['status']=status
        if status=='active':occupied.update(keys)
    return changes
