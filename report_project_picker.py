"""工作报告与个人任务共用的项目选择目录。"""
from uuid import UUID
from datetime import datetime, timedelta
from calendar import monthrange
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload
from models import AppUser, TranslationProject, Consultation, Client, SubClient
from chat_time import now
from interpretation_models import InterpretationProject
from annotation_models import AnnotationProject
from recruitment_models import RecruitmentProject
from search_matching import keyword_any
from workflow_models import ProjectWorkbenchResponsibility

PROJECT_MODELS={'笔译项目':TranslationProject,'口译项目':InterpretationProject,'标注项目':AnnotationProject,'招聘项目':RecruitmentProject,
                '配音项目':TranslationProject,'字幕项目':TranslationProject,'公证项目':TranslationProject,'认证项目':TranslationProject,'新咨询对接':Consultation}
PROJECT_MODELS['（音视频）转录/字幕项目'] = TranslationProject


def query_projects(db,project_type):
    model=PROJECT_MODELS.get(project_type)
    if not model:
        raise HTTPException(422,'请选择已有项目类型')
    query=db.query(model)
    if project_type in {'（音视频）转录/字幕项目', '字幕项目'}:
        query=query.filter(TranslationProject.task_type.in_(['（音视频）转录/字幕项目', '字幕项目']))
    elif model is TranslationProject and project_type!='笔译项目':
        query=query.filter(TranslationProject.task_type==project_type)
    return model,query


def identity(row,project_type):
    client=getattr(row,'sub_client',None) or getattr(row,'client',None)
    return {'id':str(row.id),'project_type':project_type,'order_no':getattr(row,'order_no',None) or getattr(row,'consultation_code',''),
            'project_name':getattr(row,'source_file_name',None) or getattr(row,'project_name',None) or getattr(row,'consultation_code',''),
            'client_name':getattr(client,'client_name','') or '', 'client_short_name':getattr(client,'client_short_name','') or '',
            'translation_direction':getattr(row,'language_pair',None) or ''}


def order_date_range(period, today=None):
    today=today or now().date()
    if period=='all':return None,None
    if period=='week':start=today-timedelta(days=6)
    elif period in ('month','quarter','year'):
        months={'month':1,'quarter':3,'year':12}[period]
        year,month=divmod(today.year*12+today.month-1-months,12);month+=1
        start=today.replace(year=year,month=month,day=min(today.day,monthrange(year,month)[1]))
    else:raise HTTPException(422,'请选择有效订单时间范围')
    return start,today+timedelta(days=1)


STATUS_ALIASES = {
    TranslationProject: {
        'pending_confirmation': ('pending',),
        'confirmed': ('in_progress',),
        'sent_to_client': ('completed',),
        'cancelled': ('terminated',),
    },
    AnnotationProject: {
        'initial_consultation': ('pending_confirmation',),
        'trial_in_progress': ('trial',),
        'project_in_progress': ('in_progress',),
    },
    InterpretationProject: {'cancelled': ('取消',)},
    Consultation: {'following': ('pending',)},
}


def search(db,project_type,keyword,page,page_size,period='all',client_keyword='',direction_keyword='',*,
           scope_filter=None, manager_keyword='', project_status='', status_label=''):
    model,query=query_projects(db,project_type)
    client_fields=[]
    if hasattr(model,'client_id'):
        query=query.outerjoin(Client,model.client_id==Client.id).options(joinedload(model.client))
        client_fields.extend([Client.client_name,Client.client_short_name])
    if hasattr(model,'sub_client_id'):
        query=query.outerjoin(SubClient,model.sub_client_id==SubClient.id).options(joinedload(model.sub_client))
        client_fields.extend([SubClient.client_name,SubClient.client_short_name])
    if scope_filter is not None:
        query=query.filter(scope_filter)
    number=model.consultation_code if model is Consultation else model.order_no
    fields=[number,model.project_name,*client_fields]
    direction=getattr(model,'language_pair',None)
    if direction is not None:fields.append(direction)
    if model is TranslationProject:fields.append(model.source_file_name)
    if keyword:query=query.filter(keyword_any(fields,keyword))
    if client_keyword and client_fields:query=query.filter(keyword_any(client_fields,client_keyword))
    if direction_keyword:
        if direction is not None:query=query.filter(keyword_any([direction],direction_keyword))
        else:query=query.filter(False)
    status_column = model.status if model is Consultation else model.project_status
    if project_status:
        statuses = (project_status, *STATUS_ALIASES.get(model, {}).get(project_status, ()))
        if status_label:
            statuses += (status_label,)
        query = query.filter(func.lower(func.trim(status_column)).in_(value.lower() for value in statuses))

    manager_match = keyword_any([AppUser.full_name, AppUser.username], manager_keyword)
    if model is TranslationProject:
        if manager_keyword:
            query = query.filter(model.project_manager.has(manager_match))
        manager_load = joinedload(model.project_manager)
    elif model is Consultation:
        manager_load = None
    else:
        role = ProjectWorkbenchResponsibility
        managers = model.workbench_responsibilities.and_(role.role_code == 'project_manager')
        if manager_keyword:
            query = query.filter(model.workbench_responsibilities.any(
                (role.role_code == 'project_manager') & role.assignee.has(manager_match)
            ))
        manager_load = selectinload(managers).joinedload(role.assignee)
    start,end=order_date_range(period)
    if start:query=query.filter(model.created_at>=datetime.combine(start,datetime.min.time()),model.created_at<datetime.combine(end,datetime.min.time()))
    total=query.count()
    if manager_load is not None:
        query = query.options(manager_load)
    rows=query.order_by(model.created_at.desc(),model.id).offset((page-1)*page_size).limit(page_size).all()
    items = []
    aliases = {alias: canonical for canonical, values in STATUS_ALIASES.get(model, {}).items() for alias in values}
    for row in rows:
        if model is TranslationProject:
            names = [row.project_manager_name] if row.project_manager_name else []
        elif model is Consultation:
            names = []
        else:
            names = [
                role.assignee.full_name or role.assignee.username for role in row.workbench_responsibilities
                if role.role_code == 'project_manager' and role.assignee
            ]
        status = (row.status if model is Consultation else row.project_status) or ''
        items.append({**identity(row, project_type), 'project_manager_names': list(dict.fromkeys(names)),
                      'project_status': aliases.get(status.strip().lower(), status.strip())})
    return {'items':items,'total':total,'date_from':start.isoformat() if start else None,'date_to':(end-timedelta(days=1)).isoformat() if end else None}


def resolve(db,project_type,project_id):
    model,query=query_projects(db,project_type)
    try:uid=UUID(str(project_id))
    except (ValueError,TypeError):raise HTTPException(422,'请重新选择项目')
    row=query.filter(model.id==uid).first()
    if not row:raise HTTPException(404,'项目不存在或不属于所选项目类型')
    return identity(row,project_type)
