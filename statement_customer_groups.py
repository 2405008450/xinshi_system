"""按账单月份管理客户单据需求，复用项目单据字段。"""
from hashlib import sha256
import json
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, case, select, or_,inspect
from sqlalchemy.orm import joinedload, selectinload
from models import Client, SubClient, TranslationProject, TranslationSubOrder
from annotation_progress_time import business_now
import crud
import translation_document_requirements as documents
from search_matching import keyword_any


class CustomerGroupMove(BaseModel):
    model_config=ConfigDict(extra='forbid')
    billing_month:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    statement_required:bool
    period_number:int|None=Field(default=None,ge=1)
    expected_version:str=Field(min_length=64,max_length=64)
    manager_ids:list[UUID]=Field(default_factory=list,max_length=2000)
    only_mine:bool=False
    client_manager:str|None=None
    settlement_scope:documents.StatementScope|None=None


def project_query(db,month,manager_scope=None):
    query=db.query(TranslationProject).options(
        joinedload(TranslationProject.client),
        joinedload(TranslationProject.sub_client).joinedload(SubClient.parent_client),
        selectinload(TranslationProject.customer_charge_items),
        selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.customer_charge_items),
    ).outerjoin(Client,Client.id==TranslationProject.client_id).outerjoin(SubClient,SubClient.id==TranslationProject.sub_client_id).filter(TranslationProject.annotation_migrated_at.is_(None))
    return crud._apply_translation_project_filters(query,field_filters={**({'finance_billing_month':{'value':month}} if month else {}),**(manager_scope or {})})


def snapshot_version(rows, workspace_revision):
    return sha256(json.dumps({
        'projects': [(str(row.id), str(row.updated_at), bool(row.required)) for row in rows],
        'workspace_revision': workspace_revision,
    }).encode()).hexdigest()


def snapshot(db,client_id,month,manager_scope=None,settlement_scope=None,period_number=None):
    from collections import namedtuple
    from translation_customer_finance import effective_statement_requirements
    projects=project_query(db,month,manager_scope).filter(func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)==client_id).order_by(TranslationProject.id).all()
    required=effective_statement_requirements(db,projects)
    entry=namedtuple('StatementRequirement','id updated_at required')
    rows=[entry(project.id,project.updated_at,required[project.id]) for project in projects
          if documents.matches_statement_scope(project,settlement_scope)
          and (period_number is None or project.settlement_period_number==period_number)]
    from customer_statement_workspace import StatementWorkspace
    workspace=db.get(StatementWorkspace,client_id) if inspect(db.connection()).has_table(StatementWorkspace.__tablename__) else None
    version=snapshot_version(rows, workspace.revision if workspace else 0)
    return rows,version


def pending_clients(db,month,manager_scope=None,settlement_scope=None,*,keyword=None,client_ids=None):
    from customer_statement_workspace import StatementWorkspace
    if not inspect(db.connection()).has_table(StatementWorkspace.__tablename__):return {}
    query=db.query(StatementWorkspace.client_id)
    if client_ids is not None:
        query=query.filter(StatementWorkspace.client_id.in_(client_ids))
    if keyword and keyword.strip():
        child_parents=select(SubClient.parent_client_id).where(keyword_any(
            [SubClient.client_name,SubClient.client_short_name,SubClient.sub_client_code],keyword.strip()))
        matches=select(Client.id).where(or_(keyword_any(
            [Client.client_name,Client.client_short_name,Client.client_code],keyword.strip()),Client.id.in_(child_parents)))
        query=query.filter(StatementWorkspace.client_id.in_(matches))
    if db.get_bind().dialect.name=='postgresql':
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSONB
        # 由数据库提取当月待入账项目，避免下载所有客户的完整 roots/订单快照。
        tasks=func.jsonb_path_query_array(cast(StatementWorkspace.payload['tasks'],JSONB),
            '$.* ? (@.pending == true && @.month == $month)',cast({'month':month},JSONB))
        result={client:tasks for client,tasks in query.add_columns(tasks) if tasks}
    else:
        result={client:tasks for client,values in query.add_columns(StatementWorkspace.payload['tasks'])
                if (tasks:=[task for task in (values or {}).values() if task.get('pending') is True and task.get('month')==month])}
    if manager_scope or settlement_scope:
        roots={UUID(line['root_id']) for tasks in result.values() for task in tasks for line in task['rows']}
        projects=project_query(db,None,manager_scope).filter(TranslationProject.id.in_(roots)).all() if roots else []
        if settlement_scope:
            documents.attach(db,projects)
        matched={str(project.id) for project in projects if documents.matches_statement_scope(project,settlement_scope)}
        result={uid:[task for task in tasks if any(line['root_id'] in matched for line in task['rows'])] for uid,tasks in result.items()}
        result={uid:tasks for uid,tasks in result.items() if tasks}
    return result


def customers(db,month,required,keyword,skip,limit,manager_scope=None,progress=None,settlement_scope=None,period_number=None):
    from translation_customer_finance import effective_statement_requirements
    special_view=settlement_scope=='special'
    waiting=pending_clients(db,month,manager_scope,settlement_scope,keyword=keyword) if not special_view or required else {}
    project_scope_query=project_query(db,month,manager_scope)
    if keyword and keyword.strip():
        # 先确定匹配的母客户，再保留这些客户的完整项目范围；不能按命中的单个子客户截断计数。
        customer=func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)
        parent_matches=select(Client.id).where(keyword_any(
            [Client.client_name,Client.client_short_name,Client.client_code],keyword.strip()))
        matching_clients=project_scope_query.with_entities(customer.label('client_id')).filter(or_(
            customer.in_(parent_matches),
            keyword_any([SubClient.client_name,SubClient.client_short_name,SubClient.sub_client_code],keyword.strip()),
        )).distinct().subquery()
        project_scope_query=project_scope_query.filter(customer.in_(select(matching_clients.c.client_id)))
    projects=project_scope_query.all()
    requirements=effective_statement_requirements(db,projects)
    project_scope='standard' if special_view and not required else settlement_scope
    scoped_projects=[project for project in projects if documents.matches_statement_scope(project,project_scope)
                     and (period_number is None or project.settlement_period_number == period_number)]
    if period_number is not None:
        ids={str(project.id) for project in scoped_projects}
        waiting={client:[task for task in tasks if all(line['root_id'] in ids for line in task['rows'])]
                 for client,tasks in waiting.items()}
        waiting={client:tasks for client,tasks in waiting.items() if tasks}
    base=project_query(db,month,manager_scope).filter(TranslationProject.id.in_([project.id for project in scoped_projects])).with_entities(
        func.coalesce(TranslationProject.client_id,SubClient.parent_client_id).label('client_id'),
        TranslationProject.id.in_([project_id for project_id, value in requirements.items() if value]).label('required'),
    ).subquery()
    grouped=select(base.c.client_id,func.count().label('project_count'),func.sum(case((base.c.required.is_(True),1),else_=0)).label('required_count')).group_by(base.c.client_id).subquery()
    query=db.query(Client,grouped.c.project_count,grouped.c.required_count).outerjoin(grouped,Client.id==grouped.c.client_id)
    if special_view:
        special_clients={project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)
                         for project in projects if documents.matches_statement_scope(project,'special')
                         and (period_number is None or project.settlement_period_number==period_number)}
        special_clients.discard(None)
        if required:
            query=query.filter(or_(grouped.c.project_count>0,Client.id.in_(list(waiting))))
        else:
            query=query.filter(grouped.c.project_count>0,Client.id.notin_(special_clients))
    else:
        query=query.filter(or_(grouped.c.required_count>0,Client.id.in_(list(waiting))) if required else (grouped.c.required_count==0)&Client.id.notin_(list(waiting)))
    from customer_statement_progress import StatementProgress,ready
    progress_ready=ready(db)
    if progress:
        if progress_ready:query=query.outerjoin(StatementProgress,(StatementProgress.client_id==Client.id)&(StatementProgress.billing_month==month)).filter(func.coalesce(StatementProgress.progress,'not_started')==progress)
        elif progress!='not_started':query=query.filter(False)
    from search_matching import matches_keywords
    child_match = {}
    if keyword and keyword.strip():
        eligible_ids={project.sub_client_id for project in scoped_projects if project.sub_client_id}
        child_match={child.id:child.parent_client_id for child in db.query(SubClient).filter(
            SubClient.id.in_(eligible_ids),
            keyword_any([SubClient.client_name,SubClient.client_short_name,SubClient.sub_client_code],keyword.strip()))}
        query=query.filter(or_(keyword_any([Client.client_name,Client.client_short_name,Client.client_code],keyword.strip()),
                               Client.id.in_(set(child_match.values()))))
    total=query.count();items=[]
    selected_clients=query.order_by(Client.client_short_name,Client.client_name,Client.id).offset(skip).limit(limit).all()
    from collections import namedtuple
    from customer_statement_workspace import StatementWorkspace
    entry=namedtuple('StatementRequirement','id updated_at required')
    version_rows={client.id: [] for client, _, _ in selected_clients}
    for project in sorted(projects, key=lambda project: project.id):
        client_id=project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)
        if client_id in version_rows and documents.matches_statement_scope(project,settlement_scope) and (period_number is None or project.settlement_period_number==period_number):
            version_rows[client_id].append(entry(project.id,project.updated_at,requirements[project.id]))
    revisions=dict(db.query(StatementWorkspace.client_id, StatementWorkspace.revision).filter(
        StatementWorkspace.client_id.in_(version_rows),
    ).all()) if version_rows and inspect(db.connection()).has_table(StatementWorkspace.__tablename__) else {}
    for client,count,required_count in selected_clients:
        version=snapshot_version(version_rows[client.id],revisions.get(client.id,0))
        parent_matches=matches_keywords(' '.join(filter(None,(client.client_name,client.client_short_name,client.client_code))),keyword)
        items.append(dict(id=str(client.id),name=client.client_name,short_name=client.client_short_name or client.client_name,code=client.client_code,project_count=count or 0,required_count=required_count or 0,pending_count=len(waiting.get(client.id,[])),version=version,
                          sub_clients=[],filter_sub_clients=not parent_matches))
    managers={item['id']:set() for item in items}
    if items:
        client_ids={UUID(item['id']) for item in items}
        projects=[project for project in scoped_projects if
                  (project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)) in client_ids]
        monthly_ids={project.id for project in projects}
        roots={line['root_id'] for item in items for task in waiting.get(UUID(item['id']),[]) for line in task['rows']}
        if roots:projects=list({project.id:project for project in projects+db.query(TranslationProject).filter(TranslationProject.id.in_([UUID(uid) for uid in roots])).all()}.values())
        from project_client_manager import attach
        attach(db,'translation',projects)
        items_by_id={item['id']:item for item in items}
        child_entries={}
        for project in projects:
            crud._attach_project_client_fields(project)
            client_id=str(project.client_id or project.sub_client.parent_client_id)
            if project.id in monthly_ids and client_id in managers:
                managers[client_id].add(project.client_manager or '未分配')
            child=project.sub_client
            item=items_by_id.get(client_id)
            if not child or not item or (item['filter_sub_clients'] and child.id not in child_match):continue
            entry=child_entries.get(child.id)
            if entry is None:
                entry=dict(id=str(child.id),name=child.client_short_name or child.client_name,code=child.sub_client_code,
                           statement_project_count=0,statement_required_count=0,pending_count=0)
                child_entries[child.id]=entry;item['sub_clients'].append(entry)
            if documents.payment_method(project)=='sub_client':
                entry['statement_project_count']+=1
                entry['statement_required_count']+=int(requirements.get(project.id,str(project.id) in roots))
                entry['pending_count']+=int(str(project.id) in roots)
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
        rows,version=snapshot(db,client_id,payload.billing_month,scope,payload.settlement_scope,payload.period_number)
        if version!=payload.expected_version:raise HTTPException(409,'客户项目或单据需求已变化，请刷新后重试')
        if not payload.statement_required and client_id in pending_clients(db,payload.billing_month,scope,payload.settlement_scope,client_ids={client_id}):raise HTTPException(422,'该客户当月仍有待入账项目，请先调整或撤销待入账项目')
        if not rows:raise HTTPException(422,'该客户在所选账单月份没有项目')
        before={row.id:bool(row.required) for row in rows};changed=0
        projects=[project for project in projects if project.id in before]
        from translation_customer_finance import effective_statement_requirements
        effective_statement_requirements(db,projects)
        for project in projects:
            if before[project.id]==payload.statement_required:continue
            documents.save(db,project,statement_required=payload.statement_required,actor_id=user.id)
            project.updated_at=business_now().replace(tzinfo=None);changed+=1
        from customer_statements import auto_sync_document_defaults
        import sub_client_finance
        sub_ids={project.sub_client_id for project in projects if project.sub_client_id and project.settlement_party!='client'}
        for sub_id in sub_ids:
            sub_client_finance.write_preferences(db,sub_id,{'statement_required':payload.statement_required},user,revision=None)
        if any(not project.sub_client_id or project.settlement_party=='client' for project in projects):
            auto_sync_document_defaults(db,user,client_id,statement_default='required' if payload.statement_required else 'not_required')
        db.commit()
        return dict(client_id=str(client_id),billing_month=payload.billing_month,statement_required=payload.statement_required,affected_count=changed)
    except Exception:
        db.rollback();raise
