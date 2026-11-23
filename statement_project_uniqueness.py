"""普通结算项目只能归属一份有效对账单；特殊结算显式允许跨单。"""
from uuid import UUID
from copy import deepcopy
from fastapi import HTTPException
from sqlalchemy import inspect,or_,cast,func
from models import TranslationProject
from statement_document_status import normalize


def memberships(payload):
    active={board['id']:board for board in payload['boards'] if board.get('status')!='void'}
    result={}
    for task in payload['tasks'].values():
        if task.get('pending') or task.get('board_id') not in active:continue
        board=active[task['board_id']]
        if board.get('settlement_scope')=='special':continue
        for line in task['rows']:result.setdefault(line['root_id'],{})[board['id']]=board.get('name','对账单')
    return result


def validate(db,client_id,payload):
    from customer_statement_workspace import StatementWorkspace
    from translation_document_requirements import attach
    from translation_customer_finance import payment_method
    current=memberships(payload)
    if not current:return
    projects=db.query(TranslationProject).filter(TranslationProject.id.in_([UUID(uid) for uid in current])).order_by(TranslationProject.id).with_for_update().all()
    attach(db,projects)
    ordinary=set(current)-{str(project.id) for project in projects if payment_method(project)=='special'}
    if not ordinary:return
    related=db.query(StatementWorkspace.payload['boards'],StatementWorkspace.payload['tasks']).filter(StatementWorkspace.client_id!=client_id)
    dialect=db.get_bind().dialect.name
    if dialect=='postgresql':
        from sqlalchemy.dialects.postgresql import JSONB
        roots=cast(StatementWorkspace.payload,JSONB)['roots']
        related=related.filter(or_(*(roots.op('?')(uid) for uid in ordinary)))
    elif dialect=='sqlite':
        related=related.filter(or_(*(func.json_type(StatementWorkspace.payload,f'$.roots."{uid}"').isnot(None) for uid in ordinary)))
    staged=db.info.get('statement_pending_payloads',{})
    if staged:related=related.filter(StatementWorkspace.client_id.notin_(staged))
    other_payloads=[(boards,tasks) for boards,tasks in related]
    other_payloads.extend((deepcopy(value['boards']),value['tasks']) for uid,value in staged.items() if uid!=client_id)
    for boards,tasks in other_payloads:
        other={'boards':boards or [],'tasks':tasks or {}};normalize(other)
        for uid,values in memberships(other).items():
            if uid in ordinary:current[uid].update(values)
    conflicts=[uid for uid in ordinary if len(current[uid])>1]
    if conflicts:
        by_id={str(project.id):project for project in projects}
        raise HTTPException(409,dict(code='project_multiple_active_statements',
            message='同一项目不能同时在两份有效对账单内。如需分配到多份对账单，请在财务主表把“结款模式”调整为“特殊结算”。',
            projects=[{'project_id':uid,'order_no':by_id[uid].order_no if uid in by_id else uid,'statements':list(current[uid].values())} for uid in sorted(conflicts)]))
