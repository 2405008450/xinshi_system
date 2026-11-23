"""将指定历史账单版本恢复为有效；先预览同月份、同期次冲突。"""
import copy,hashlib,json
from uuid import UUID
from fastapi import HTTPException
from statement_document_status import normalize,activate,months


def proposal(db,user,client_id,payload,data,scope=None):
    from customer_statement_workspace import StatementWorkspaceHistory,board_by_id,scoped_payload,display_data,ROW_FIELDS
    import statement_access as access
    version=str(data.get('version_id',''));uid=data.get('board_id');status=data.get('status')
    if status not in ('active','void'):raise HTTPException(422,'请选择有效或废除状态')
    current=next((board for board in payload['boards'] if board['id']==uid),None)
    if status=='void':
        if current is None or current.get('status')=='void' or current.get('active_history_id')!=version:raise HTTPException(409,'该历史版本当前不是有效版本，请刷新后操作')
        current['status']='void'
        return {'board_id':uid,'version_id':version,'status':status,'conflicts':[],'plan':''}
    if version.startswith('current:'):
        if version!='current:'+str(uid):raise HTTPException(422,'历史账单标识不一致')
        source=copy.deepcopy(payload);doc=None
    else:
        try:history_id=UUID(version)
        except ValueError:raise HTTPException(404,'历史版本不存在')
        event=db.query(StatementWorkspaceHistory).filter_by(id=history_id,client_id=client_id).first()
        if not event:raise HTTPException(404,'历史版本不存在')
        docs=[*event.changes.get('archive',{}).get('documents',[]),*event.changes.get('generation',{}).get('documents',[])]
        doc=next((board for board in docs if board['id']==uid),None)
        source=copy.deepcopy(event.after if any(board['id']==uid for board in event.after['boards']) else event.before)
        if doc is None and not any(board['id']==uid for board in event.changes.get('deleted_boards',[])):raise HTTPException(404,'历史版本中没有这份账单')
    source=scoped_payload(db,source,scope)
    access.require(db,user,access.content_clients(client_id,source),'edit_content')
    restored=copy.deepcopy(board_by_id(source,uid))
    restored['status']='active';restored['active_history_id']=version;restored.pop('archived_revision',None)
    if doc:
        for row in doc['statement']['rows']:
            key=row.get('_row_id') or row.get('line_id')
            if key:restored.setdefault('overrides',{})[key]={field:row[field] for field in ROW_FIELDS-{'remarks'} if field in row}
    existing_documents=[]
    if current and current.get('status')!='void' and current.get('active_history_id')!=version:
        existing_documents.append(dict(id=uid,name=current['name'],status='void',settlement_scope=current.get('settlement_scope'),statement=display_data(payload,current),reason='切换历史版本'))
    candidate=copy.deepcopy(payload)
    candidate['boards']=[board for board in candidate['boards'] if board['id']!=uid]+[restored]
    source_tasks={key:copy.deepcopy(task) for key,task in source['tasks'].items() if task.get('board_id')==uid}
    candidate['tasks']={key:task for key,task in candidate['tasks'].items() if task.get('board_id')!=uid}
    candidate['tasks'].update(source_tasks)
    activate(candidate,restored)
    changes=normalize(candidate)
    conflicts=[change for change in changes if change['board_id']!=uid]
    source_tasks={key:copy.deepcopy(task) for key,task in source['tasks'].items() if task.get('board_id')==uid}
    # 恢复单据是明确的版本切换；不能把当前其他有效账单内的项目悄悄移走。
    active={board['id'] for board in candidate['boards'] if board.get('status')!='void' and board['id']!=uid}
    from statement_project_uniqueness import memberships
    old_memberships=memberships(payload)
    for task in source_tasks.values():
        for line in task['rows']:
            other={key:name for key,name in old_memberships.get(line['root_id'],{}).items() if key in active}
            if other:
                from models import TranslationProject
                from translation_document_requirements import attach
                from translation_customer_finance import payment_method
                project=db.get(TranslationProject,UUID(line['root_id']))
                if project:attach(db,[project])
                if project is None or payment_method(project)!='special':raise HTTPException(409,'该项目已在另一份有效对账单内。如需同时归属多份，请在财务主表把“结款模式”调整为“特殊结算”。')
    candidate['tasks']={key:task for key,task in candidate['tasks'].items() if task.get('board_id')!=uid}
    candidate['tasks'].update(source_tasks)
    candidate['roots'].update(copy.deepcopy(source.get('roots',{})))
    signature=hashlib.sha256(json.dumps({'version':version,'board':uid,'conflicts':conflicts,'current_version':current.get('active_history_id') if current else None},sort_keys=True).encode()).hexdigest()
    payload.clear();payload.update(candidate)
    return {'board_id':uid,'version_id':version,'status':status,'conflicts':conflicts,'plan':signature,'superseded':existing_documents}
