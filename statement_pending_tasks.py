"""待入账项目保存在既有客户工作区中；同一项目仅有一个状态和归属。"""
import copy
from fastapi import HTTPException
from annotation_progress_time import business_now


def pending(task):
    return task.get('pending') is True


def invalidate_overrides(payload,task):
    roots={line['root_id'] for line in task['rows']}
    for board in payload['boards']:
        board['overrides']={key:value for key,value in board.get('overrides',{}).items() if not any(key.startswith('summary:'+root+':') for root in roots)}


def schedule(payload,ids,month,actor,target=None):
    changes=[]
    for task_id in ids:
        task=payload['tasks'][task_id]
        before={'month':task['month'],'board_id':task['board_id'],'pending':pending(task),'target_board_id':task.get('pending_target_board_id')}
        if not pending(task):task['pending_from']={'month':task['month'],'board_id':task['board_id']}
        task.update(board_id=None,month=month,pending=True,pending_actor=actor.full_name or actor.username,pending_at=business_now().isoformat())
        if target:task['pending_target_board_id']=target['id']
        else:task.pop('pending_target_board_id',None)
        invalidate_overrides(payload,task)
        changes.append({'task_id':task_id,'order_no':task['rows'][0]['order_no'],'before':before,'after':{'month':month,'board_id':None,'pending':True,'target_board_id':target['id'] if target else None,'period_number':target.get('period_number') if target else None}})
    return changes


def cancel(payload,ids):
    changes=[]
    for task_id in ids:
        task=payload['tasks'][task_id]
        if not pending(task):raise HTTPException(409,'项目已纳入对账单，请刷新后操作')
        previous=task.get('pending_from')
        if not previous or not any(board['id']==previous['board_id'] for board in payload['boards']):raise HTTPException(409,'原对账单已删除，请调整目标月份或从修改记录恢复')
        changes.append({'task_id':task_id,'order_no':task['rows'][0]['order_no'],'before':{'month':task['month'],'pending':True},'after':previous})
        task.update(copy.deepcopy(previous));task['pending']=False
        for key in ('pending_from','pending_actor','pending_at','pending_target_board_id'):task.pop(key,None)
        invalidate_overrides(payload,task)
    return changes


def accept(payload,months,target_board):
    changes=[]
    for task in payload['tasks'].values():
        if not pending(task) or task['month'] not in months:continue
        board=target_board(task)
        task.update(board_id=board['id'],pending=False)
        task.pop('pending_target_board_id',None)
        invalidate_overrides(payload,task)
        changes.append({'task_id':task['id'],'order_no':task['rows'][0]['order_no'],'month':task['month'],'board_id':board['id'],'board_name':board['name']})
    return changes


def summaries(payload):
    return [{'id':task['id'],'order_no':task['rows'][0]['order_no'],'project_name':task['rows'][0]['project_name'],
             'sub_client_id':task['rows'][0].get('sub_client_id'),'month':task['month'],
             'actor_name':task.get('pending_actor',''),'created_at':task.get('pending_at','')}
            for task in payload['tasks'].values() if pending(task)]
