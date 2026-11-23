"""特殊结算单是独立快照；单内增删、金额和备注不回写项目财务。"""
from copy import deepcopy
from uuid import UUID,uuid4
from fastapi import HTTPException


def is_special(board):
    return board.get('settlement_scope')=='special'


def validate_invoice_proofs(db,proofs):
    from editor_screenshot_service import references,valid_references,ready,api_time,now,promote_business_references
    from editor_screenshot_models import EditorScreenshot
    refs=references(proofs)
    if not refs:return
    if refs!=valid_references(proofs):raise HTTPException(422,'发票截图引用无效')
    if not ready(db):raise HTTPException(503,'截图功能尚未初始化')
    images=db.query(EditorScreenshot).filter(EditorScreenshot.id.in_(refs)).all()
    if len(images)!=len(refs) or any(not image.blob_sha256 or image.expires_at and api_time(image.expires_at)<=now() for image in images):raise HTTPException(422,'发票截图不存在或已过期')
    promote_business_references(db,refs)


def import_documents(db,user,client,row,before,payload,data,statements,mode):
    from customer_statement_workspace import new_board,board_by_id,imported_fields,outline,save,serialize
    import customer_statements as source
    months=sorted(set(data.months))
    if data.board_id:
        board=board_by_id(payload,data.board_id)
        if not is_special(board) or board.get('status')=='void':raise HTTPException(422,'请选择有效的特殊结算对账单')
    else:
        board=new_board(payload,imported_fields(statements[0]),'、'.join(months)+' 对账单')
        board.update(settlement_scope='special',tax_included=statements[0]['tax_included'])
    board['billing_months']=sorted(set(board.get('billing_months',[]))|set(months))
    added=0;existing=0;generated={}
    represented={task.get('source_task_id') or task['rows'][0]['task_id'] for task in payload['tasks'].values() if task.get('board_id')==board['id']}
    for month,statement in zip(months,statements):
        grouped={}
        for line in statement['rows']:grouped.setdefault(line['task_id'],[]).append(deepcopy(line))
        for source_id,lines in grouped.items():
            if source_id in represented:existing+=1;continue
            key=str(uuid4())
            for line in lines:
                root=line['root_id']
                if root not in payload['roots']:payload['roots'][root]=outline(source.finance.read(db,UUID(root))['item'])
            task=dict(id=key,source_task_id=source_id,board_id=board['id'],month=month,rows=lines,
                      original=dict(rows=deepcopy(lines),month=month,board_id=board['id']))
            payload['tasks'][key]=task;generated[key]=task;represented.add(source_id);added+=1
    if not added and not existing:raise HTTPException(422,'当前筛选没有可生成的项目')
    row=save(db,user,client.id,row,before,payload,'生成特殊结算对账单',dict(board_id=board['id'],added_tasks=added,existing_tasks_kept=existing),
             generation=(data,mode,generated) if generated else None)
    return {**serialize(row,mode,user=user,db=db,settlement_scope='special'),
            'imported':added,'existing':existing,'excluded':0,'accepted_pending_count':0,'generation_saved':bool(generated)}


def local_note(payload,board_id,row_id,text,mode):
    from customer_statement_workspace import board_by_id,display_data
    if not isinstance(text,str) or len(text)>5000:raise HTTPException(422,'备注最多5000字')
    board=board_by_id(payload,board_id)
    if not is_special(board):raise HTTPException(422,'请选择特殊结算对账单')
    row=next((item for item in display_data(payload,board,mode,group_directions=False)['rows'] if item['_row_id']==row_id),None)
    if row is None:raise HTTPException(409,'项目已变化，请重新加载')
    previous=row.get('remarks','')
    board.setdefault('overrides',{}).setdefault(row_id,{})['remarks']=text
    return dict(board_id=board_id,before=previous,after=text)


def remove_projects(payload,board_id,ids):
    from customer_statement_workspace import board_by_id
    board=board_by_id(payload,board_id)
    if not is_special(board):raise HTTPException(422,'仅特殊结算单支持在本单移除项目')
    if not isinstance(ids,list) or not ids or any(uid not in payload['tasks'] or payload['tasks'][uid].get('board_id')!=board_id for uid in ids):
        raise HTTPException(422,'请选择本对账单的项目')
    from statement_pending_tasks import invalidate_overrides
    for uid in set(ids):
        invalidate_overrides(payload,payload['tasks'][uid]);payload['tasks'].pop(uid)
    return dict(board_id=board_id,removed_tasks=ids)
