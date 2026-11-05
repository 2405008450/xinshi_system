"""按账单月份管理客户单据需求，复用项目单据字段。"""
from hashlib import sha256
import json
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, case, select, or_,inspect
from models import Client, SubClient, TranslationProject
from annotation_progress_time import business_now
import crud
import translation_document_requirements as documents
from search_matching import keyword_any


class CustomerGroupMove(BaseModel):
    model_config=ConfigDict(extra='forbid')
    billing_month:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    statement_required:bool
    expected_version:str=Field(min_length=64,max_length=64)
    manager_ids:list[UUID]=Field(default_factory=list,max_length=2000)
    only_mine:bool=False
    client_manager:str|None=None


def project_query(db,month,manager_scope=None):
    query=db.query(TranslationProject).outerjoin(Client,Client.id==TranslationProject.client_id).outerjoin(SubClient,SubClient.id==TranslationProject.sub_client_id).filter(TranslationProject.annotation_migrated_at.is_(None))
    return crud._apply_translation_project_filters(query,field_filters={**({'finance_billing_month':{'value':month}} if month else {}),**(manager_scope or {})})


def snapshot(db,client_id,month,manager_scope=None):
    rows=project_query(db,month,manager_scope).filter(func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)==client_id).order_by(TranslationProject.id).with_entities(TranslationProject.id,TranslationProject.updated_at,documents.required_expression(db).label('required')).all()
    from customer_statement_workspace import StatementWorkspace
    workspace=db.get(StatementWorkspace,client_id) if inspect(db.connection()).has_table(StatementWorkspace.__tablename__) else None
    version=sha256(json.dumps({'projects':[(str(row.id),str(row.updated_at),bool(row.required)) for row in rows],'workspace_revision':workspace.revision if workspace else 0}).encode()).hexdigest()
    return rows,version


def pending_clients(db,month,manager_scope=None):
    from customer_statement_workspace import StatementWorkspace
    if not inspect(db.connection()).has_table(StatementWorkspace.__tablename__):return {}
    result={row.client_id:tasks for row in db.query(StatementWorkspace).all() if (tasks:=[task for task in row.payload.get('tasks',{}).values() if task.get('pending') is True and task.get('month')==month])}
    if manager_scope:
        roots={UUID(line['root_id']) for tasks in result.values() for task in tasks for line in task['rows']}
        matched={str(uid) for uid, in project_query(db,None,manager_scope).filter(TranslationProject.id.in_(roots)).with_entities(TranslationProject.id).all()} if roots else set()
        result={uid:[task for task in tasks if any(line['root_id'] in matched for line in task['rows'])] for uid,tasks in result.items()}
        result={uid:tasks for uid,tasks in result.items() if tasks}
    return result


def customers(db,month,required,keyword,skip,limit,manager_scope=None,progress=None):
    waiting=pending_clients(db,month,manager_scope)
    base=project_query(db,month,manager_scope).with_entities(func.coalesce(TranslationProject.client_id,SubClient.parent_client_id).label('client_id'),documents.required_expression(db).label('required')).subquery()
    grouped=select(base.c.client_id,func.count().label('project_count'),func.sum(case((base.c.required.is_(True),1),else_=0)).label('required_count')).group_by(base.c.client_id).subquery()
    query=db.query(Client,grouped.c.project_count,grouped.c.required_count).outerjoin(grouped,Client.id==grouped.c.client_id)
    query=query.filter(or_(grouped.c.required_count>0,Client.id.in_(list(waiting))) if required else (grouped.c.required_count==0)&Client.id.notin_(list(waiting)))
    from customer_statement_progress import StatementProgress,ready
    progress_ready=ready(db)
    if progress:
        if progress_ready:query=query.outerjoin(StatementProgress,(StatementProgress.client_id==Client.id)&(StatementProgress.billing_month==month)).filter(func.coalesce(StatementProgress.progress,'not_started')==progress)
        elif progress!='not_started':query=query.filter(False)
    if keyword and keyword.strip():query=query.filter(keyword_any([Client.client_name,Client.client_short_name,Client.client_code],keyword.strip()))
    total=query.count();items=[]
    for client,count,required_count in query.order_by(Client.client_short_name,Client.client_name,Client.id).offset(skip).limit(limit).all():
        _,version=snapshot(db,client.id,month,manager_scope)
        items.append(dict(id=str(client.id),name=client.client_name,short_name=client.client_short_name or client.client_name,code=client.client_code,project_count=count or 0,required_count=required_count or 0,pending_count=len(waiting.get(client.id,[])),version=version))
    managers={item['id']:set() for item in items}
    if items:
        projects=project_query(db,month,manager_scope).filter(func.coalesce(TranslationProject.client_id,SubClient.parent_client_id).in_([UUID(item['id']) for item in items])).all()
        monthly_ids={project.id for project in projects}
        roots={line['root_id'] for item in items for task in waiting.get(UUID(item['id']),[]) for line in task['rows']}
        if roots:projects=list({project.id:project for project in projects+db.query(TranslationProject).filter(TranslationProject.id.in_([UUID(uid) for uid in roots])).all()}.values())
        from project_client_manager import attach
        attach(db,'translation',projects)
        for project in projects:
            crud._attach_project_client_fields(project)
            client_id=str(project.client_id or project.sub_client.parent_client_id)
            if project.id in monthly_ids and client_id in managers:managers[client_id].add(project.client_manager or '未分配')
        by_id={str(project.id):project for project in projects}
        for item in items:
            for task in waiting.get(UUID(item['id']),[]):
                for line in task['rows']:
                    project=by_id.get(line['root_id'])
                    if project:managers[item['id']].add(project.client_manager or '未分配')
    progress_rows={str(row.client_id):row for row in db.query(StatementProgress).filter(StatementProgress.client_id.in_([UUID(item['id']) for item in items]),StatementProgress.billing_month==month).all()} if progress_ready and items else {}
    for item in items:
        item['client_managers']=sorted(managers[item['id']])
        saved=progress_rows.get(item['id']);item['progress']=saved.progress if saved else 'not_started';item['progress_revision']=saved.revision if saved else 0
    return dict(items=items,total=total)


def move(db,user,client_id:UUID,payload):
    try:
        if not db.query(Client).filter(Client.id==client_id).with_for_update().first():raise HTTPException(404,'客户不存在')
        from finance_manager_scope import manager_fields
        scope=manager_fields(db,user,payload.manager_ids,payload.only_mine,payload.client_manager)
        projects=project_query(db,payload.billing_month,scope).filter(func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)==client_id).order_by(TranslationProject.id).with_for_update(of=TranslationProject).populate_existing().all()
        rows,version=snapshot(db,client_id,payload.billing_month,scope)
        if version!=payload.expected_version:raise HTTPException(409,'客户项目或单据需求已变化，请刷新后重试')
        if not payload.statement_required and client_id in pending_clients(db,payload.billing_month,scope):raise HTTPException(422,'该客户当月仍有待入账任务，请先调整或撤销待入账任务')
        if not rows:raise HTTPException(422,'该客户在所选账单月份没有项目')
        before={row.id:bool(row.required) for row in rows};changed=0
        for project in projects:
            if before[project.id]==payload.statement_required:continue
            documents.save(db,project,statement_required=payload.statement_required,actor_id=user.id)
            project.updated_at=business_now().replace(tzinfo=None);changed+=1
        db.commit()
        return dict(client_id=str(client_id),billing_month=payload.billing_month,statement_required=payload.statement_required,affected_count=changed)
    except Exception:
        db.rollback();raise
