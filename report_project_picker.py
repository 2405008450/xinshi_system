"""工作报告与个人任务共用的最小项目身份目录，只返回编号和名称。"""
from uuid import UUID
from datetime import datetime, timedelta
from calendar import monthrange
from fastapi import HTTPException
from sqlalchemy.orm import joinedload
from models import TranslationProject, Consultation, Client, SubClient
from chat_time import now
from interpretation_models import InterpretationProject
from annotation_models import AnnotationProject
from recruitment_models import RecruitmentProject
from search_matching import keyword_any

PROJECT_MODELS={'笔译项目':TranslationProject,'口译项目':InterpretationProject,'标注项目':AnnotationProject,'招聘项目':RecruitmentProject,
                '配音项目':TranslationProject,'字幕项目':TranslationProject,'公证项目':TranslationProject,'认证项目':TranslationProject,'新咨询对接':Consultation}


def query_projects(db,project_type):
    model=PROJECT_MODELS.get(project_type)
    if not model:
        raise HTTPException(422,'请选择已有项目类型')
    query=db.query(model)
    if model is TranslationProject and project_type!='笔译项目':
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


def search(db,project_type,keyword,page,page_size,period='all',client_keyword='',direction_keyword='',*,scope_filter=None):
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
    start,end=order_date_range(period)
    if start:query=query.filter(model.created_at>=datetime.combine(start,datetime.min.time()),model.created_at<datetime.combine(end,datetime.min.time()))
    total=query.count()
    rows=query.order_by(model.created_at.desc(),model.id).offset((page-1)*page_size).limit(page_size).all()
    return {'items':[identity(row,project_type) for row in rows],'total':total,'date_from':start.isoformat() if start else None,'date_to':(end-timedelta(days=1)).isoformat() if end else None}


def resolve(db,project_type,project_id):
    model,query=query_projects(db,project_type)
    try:uid=UUID(str(project_id))
    except (ValueError,TypeError):raise HTTPException(422,'请重新选择项目')
    row=query.filter(model.id==uid).first()
    if not row:raise HTTPException(404,'项目不存在或不属于所选项目类型')
    return identity(row,project_type)
