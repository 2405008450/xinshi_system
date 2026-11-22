"""有效对账单备注与财务客户说明共用数据源；历史快照保持原文。"""
from uuid import UUID
from fastapi import HTTPException
from models import TranslationProject,TranslationSubOrder
import translation_finance_notes as notes


def refresh(db,payload):
    if db is None or not notes.ready(db):return
    active={board['id'] for board in payload['boards'] if board.get('status')!='void' and board.get('settlement_scope')!='special'}
    special={board['id'] for board in payload['boards'] if board.get('settlement_scope')=='special'}
    lines=[line for task in payload['tasks'].values() if task.get('board_id') in active or task.get('pending') and task.get('pending_from',{}).get('board_id') not in special for line in task['rows']]
    roots={UUID(line['root_id']) for line in lines}
    values={str(uid):text or '' for uid,text in db.query(notes.TranslationFinanceNote.order_id,notes.TranslationFinanceNote.customer_note).filter(notes.TranslationFinanceNote.project_id.in_(roots))} if roots else {}
    for line in lines:line['remarks']=values.get(line.get('task_id') or line['root_id'],'')
    for board in payload['boards']:
        if board['id'] not in active:continue
        for fields in board.get('overrides',{}).values():fields.pop('remarks',None)


def edit(db,user,payload,board_id,row_id,text,mode='children'):
    from customer_statement_workspace import board_by_id,display_data
    from translation_finance_audit import append_snapshots
    if not isinstance(text,str) or len(text)>5000:raise HTTPException(422,'客户说明最多5000字')
    board=board_by_id(payload,board_id)
    if board.get('settlement_scope')=='special':
        from statement_special_documents import local_note
        return local_note(payload,board_id,row_id,text,mode)
    if board.get('status')=='void':raise HTTPException(409,'历史版本不可修改客户说明')
    row=next((line for line in display_data(payload,board,mode,group_directions=False)['rows'] if line['_row_id']==row_id),None)
    if not row:raise HTTPException(409,'项目已变化，请重新加载')
    tasks=[payload['tasks'][uid] for uid in row['task_ids']]
    owners={(line['root_id'],line.get('task_id') or task['id']) for task in tasks for line in task['rows']}
    roots={root for root,_ in owners};changes=[]
    projects={str(project.id):project for project in db.query(TranslationProject).filter(TranslationProject.id.in_([UUID(uid) for uid in roots])).order_by(TranslationProject.id).with_for_update()}
    def snapshot(project):
        result={}
        for owner in [project,*project.sub_orders]:
            stored=db.get(notes.TranslationFinanceNote,owner.id) if notes.ready(db) else None
            result[str(owner.id)]=dict(order_no=getattr(owner,'sub_order_no',None) or project.order_no,project_name=getattr(owner,'sub_project_name',None) or project.project_name,customer_explanation=(stored.customer_note or '') if stored else '')
        return result
    audit_before={root:snapshot(project) for root,project in projects.items()}
    for root,uid in sorted(owners):
        project=projects.get(root)
        if project is None:raise HTTPException(409,'原项目已删除，无法同步客户说明')
        owner=project if root==uid else db.get(TranslationSubOrder,UUID(uid))
        if owner is None or owner is not project and str(owner.parent_project_id)!=root:raise HTTPException(409,'原订单已变化，无法同步客户说明')
        stored=db.get(notes.TranslationFinanceNote,UUID(uid)) if notes.ready(db) else None
        previous=stored.customer_note or '' if stored else ''
        if previous==text:continue
        order_no=getattr(owner,'sub_order_no',None) or project.order_no
        name=getattr(owner,'sub_project_name',None) or project.project_name
        before=dict(order_no=order_no,project_name=name,customer_explanation=previous)
        after={**before,'customer_explanation':text}
        notes.apply(db,user,project,owner,customer=text)
        changes.append(dict(order_no=order_no,before=previous,after=text))
    db.flush()
    for root,project in projects.items():append_snapshots(db,user,UUID(root),audit_before[root],snapshot(project))
    refresh(db,payload)
    return {'board_id':board_id,'customer_notes':changes}
