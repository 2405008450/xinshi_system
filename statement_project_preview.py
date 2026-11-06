"""从客户项目表选择的订单生成只读预览，不写对账单工作区。"""
from uuid import UUID
from decimal import Decimal
from fastapi import HTTPException
from models import TranslationProject,TranslationSubOrder,SubClient
from sqlalchemy import func

def build(db,client_id,month,order_ids,mode='children'):
    import customer_statements as statements
    ids=set(order_ids)
    roots=db.query(TranslationProject).filter(TranslationProject.id.in_(ids)).all()
    children=db.query(TranslationSubOrder).filter(TranslationSubOrder.id.in_(ids)).all()
    owners={row.id:row for row in [*roots,*children]}
    if set(owners)!=ids:raise HTTPException(422,'所选订单不存在，请刷新项目列表')
    result=None;lines={};pending=[]
    if not ids:
        root=db.query(TranslationProject).outerjoin(SubClient,TranslationProject.sub_client_id==SubClient.id).filter(func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)==client_id,TranslationProject.annotation_migrated_at.is_(None)).first()
        if root is None:raise HTTPException(422,'当前没有可预览的项目')
        result=statements.build_statement(db,root.id,None,month,'project',mode)
    for order_id in dict.fromkeys(order_ids):
        owner=owners[order_id]
        root=owner if isinstance(owner,TranslationProject) else db.get(TranslationProject,owner.parent_project_id)
        client=root.client or (root.sub_client.parent_client if root.sub_client else None)
        if not client or client.id!=client_id:raise HTTPException(422,'所选订单必须属于当前客户')
        statement=statements.build_statement(db,root.id,owner.id,month,'project',mode)
        if result is None:result=statement
        for line in statement['rows']:lines[line['line_id']]={**line,'billing_month':month,'_row_id':line['line_id']}
        pending.extend(statement['pending'])
    # 正式生成会自动接收该月待入账任务，预览须呈现同一批任务。
    from customer_statement_workspace import workspace
    from statement_pending_tasks import pending as is_pending
    saved=workspace(db,client_id)
    if saved:
        for task in saved.payload.get('tasks',{}).values():
            if is_pending(task) and task['month']==month:
                for line in task['rows']:lines[line['line_id']]={**line,'billing_month':month,'_row_id':line['line_id']}
    result['rows']=list(lines.values());result['pending']=list(dict.fromkeys(pending))
    sums={}
    for line in result['rows']:
        if line.get('counted_in_total',True) and line['subtotal'] is not None:sums[line['currency']]=sums.get(line['currency'],Decimal(0))+Decimal(line['subtotal'])
    result['totals']={currency:statements.money(amount) for currency,amount in sums.items()}
    return result
