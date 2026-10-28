"""工作报告与个人任务共用的最小项目身份目录，只返回编号和名称。"""
from uuid import UUID
from fastapi import HTTPException
from models import TranslationProject, Consultation
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
    return {'id':str(row.id),'project_type':project_type,'order_no':getattr(row,'order_no',None) or getattr(row,'consultation_code',''),
            'project_name':getattr(row,'source_file_name',None) or getattr(row,'project_name',None) or getattr(row,'consultation_code','')}


def search(db,project_type,keyword,page,page_size):
    model,query=query_projects(db,project_type)
    number=model.consultation_code if model is Consultation else model.order_no
    fields=[number,model.project_name]
    if model is TranslationProject:fields.append(model.source_file_name)
    if keyword:query=query.filter(keyword_any(fields,keyword))
    total=query.count()
    rows=query.order_by(model.created_at.desc(),model.id).offset((page-1)*page_size).limit(page_size).all()
    return {'items':[identity(row,project_type) for row in rows],'total':total}


def resolve(db,project_type,project_id):
    model,query=query_projects(db,project_type)
    try:uid=UUID(str(project_id))
    except (ValueError,TypeError):raise HTTPException(422,'请重新选择项目')
    row=query.filter(model.id==uid).first()
    if not row:raise HTTPException(404,'项目不存在或不属于所选项目类型')
    return identity(row,project_type)
