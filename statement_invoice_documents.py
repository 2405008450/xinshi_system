"""按有效特殊结算单读取开票需求，金额来自单据快照。"""
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel,Field


class StatementInvoiceRef(BaseModel):
    client_id:UUID
    board_id:UUID
    revision:int=Field(ge=1)


def read_documents(db,refs,*,check_revision=True,workspace_rows=None):
    from customer_statement_workspace import workspace,display_data,statement_number,document_status
    result=[];seen=set();number_cache={}
    for ref in refs:
        key=str(ref.board_id)
        if key in seen:raise HTTPException(422,'对账单不能重复选择')
        seen.add(key)
        row=workspace_rows.get(ref.client_id) if workspace_rows is not None else workspace(db,ref.client_id)
        if row is None or check_revision and row.revision!=ref.revision:raise HTTPException(409,'对账单内容已更新，请重新加载开票需求')
        board=next((item for item in row.payload['boards'] if item['id']==key),None)
        if not board or board.get('settlement_scope')!='special' or board.get('status')=='void':raise HTTPException(422,'请选择有效的特殊结算对账单')
        statement=display_data(row.payload,board)
        if ref.client_id not in number_cache:number_cache[ref.client_id]=statement_number.numbers(db,ref.client_id) if statement_number.ready(db) else {}
        numbers=number_cache[ref.client_id]
        statement['statement_number']=numbers.get(key,'')
        ids=list(dict.fromkeys(line['task_id'] for task in row.payload['tasks'].values() if task.get('board_id')==key for line in task['rows']))
        if not ids:raise HTTPException(422,'空对账单不能发送开票需求')
        result.append(dict(client_id=str(ref.client_id),board_id=key,revision=row.revision,name=board['name'],statement=statement,
                           project_ids=ids,totals=statement['totals'],subject_key=statement.get('subject_key'),
                           invoice_required=board.get('invoice_required'),invoice=board.get('invoice',{})))
    return result


def invoice_projects(db,documents):
    from invoice_parties import project_invoice_profile
    from models import TranslationProject,TranslationSubOrder
    projects=[]
    for document in documents:
        uid=UUID(document['project_ids'][0])
        root=db.get(TranslationProject,uid)
        if root is None:
            child=db.get(TranslationSubOrder,uid)
            root=db.get(TranslationProject,child.parent_project_id) if child else None
        if root is None:raise HTTPException(409,'对账单原项目已不存在')
        client=project_invoice_profile(db,UUID(document['client_id']))
        if document['statement']['pending']:raise HTTPException(422,'对账单金额尚未补齐，请先补全后发送开票需求')
        projects.append(dict(project_id=str(uid),root_id=str(root.id),order_no=document['statement']['statement_number'] or document['name'],
            project_name=document['name'],client_id=client['client_id'],client_name=client['client_name'],client_party=client['party'],
            default_subject=document['invoice'].get('subject_key') or document['subject_key'] or client['subject_key'],client_party_options=client.get('parties') or [client['party']],invoice_selection={'subject_key':document['subject_key'] or client['subject_key'],'invoice_type':client['invoice_type'],'revision':0},
            totals=document['totals'],statement_board_id=document['board_id']))
    return projects
