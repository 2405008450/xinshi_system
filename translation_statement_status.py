"""列表按实际对账单任务归属展示状态，不以“需对账单”代替已入账。"""
from sqlalchemy import inspect,or_,func,cast


def customer_boards(db,client_ids):
    """按客户与真实任务月份查询已生成账单，和当前项目是否入账分开。"""
    from customer_statement_workspace import StatementWorkspace
    if not client_ids or not inspect(db.connection()).has_table(StatementWorkspace.__tablename__):return {}
    result={}
    for client_id,payload in db.query(StatementWorkspace.client_id,StatementWorkspace.payload).filter(StatementWorkspace.client_id.in_(client_ids)).all():
        months={}
        for task in payload.get('tasks',{}).values():months.setdefault(task.get('board_id'),set()).add(task['month'])
        result[str(client_id)]=[{'client_id':str(client_id),'board_id':board['id'],'board_name':board['name'],'months':sorted(months[board['id']])}
            for board in payload.get('boards',[]) if months.get(board['id'])]
    return result


def attach(db,projects):
    if not projects:return
    from customer_statement_workspace import StatementWorkspace
    owners={str(owner.id):owner for project in projects for owner in [project,*project.sub_orders]}
    by_number={getattr(owner,'sub_order_no',None):key for key,owner in owners.items() if getattr(owner,'sub_order_no',None)}
    for owner in owners.values():owner.statement_status=[]
    if not inspect(db.connection()).has_table(StatementWorkspace.__tablename__):return
    by_id={str(project.id):project for project in projects}
    query=db.query(StatementWorkspace.client_id,StatementWorkspace.payload)
    if db.get_bind().dialect.name=='postgresql':
        from sqlalchemy.dialects.postgresql import JSONB
        roots=cast(StatementWorkspace.payload,JSONB)['roots']
        query=query.filter(or_(*(roots.op('?')(key) for key in by_id)))
    elif db.get_bind().dialect.name=='sqlite':
        query=query.filter(or_(*(func.json_type(StatementWorkspace.payload,f'$.roots."{key}"').isnot(None) for key in by_id)))
    for client_id,payload in query.all():
        boards={board['id']:board for board in payload.get('boards',[])}
        grouped={}
        for task in payload.get('tasks',{}).values():
            board_id=task.get('board_id')
            if board_id not in boards:continue
            for root_id in {line.get('root_id') for line in task.get('rows',[])}&by_id.keys():
                grouped.setdefault((root_id,board_id),set()).add(task['month'])
            targets={str(task.get('id'))}&owners.keys()
            for line in task.get('rows',[]):
                parts=str(line.get('order_no','')).split('.')
                targets.update(by_number[prefix] for index in range(1,len(parts)+1) if (prefix:='.'.join(parts[:index])) in by_number)
            for target in targets:grouped.setdefault((target,board_id),set()).add(task['month'])
        for (root_id,board_id),months in grouped.items():
            owners[root_id].statement_status.append({'client_id':str(client_id),'board_id':board_id,'board_name':boards[board_id]['name'],'months':sorted(months)})
    for owner in owners.values():owner.statement_status.sort(key=lambda item:(item['months'],item['board_name'],item['board_id']))
