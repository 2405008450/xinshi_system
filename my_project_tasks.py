"""工作台本人项目目录：仅按当前账号的实际经理和人员安排关系读取。"""
from fastapi import HTTPException
from sqlalchemy import case, exists, func, or_, select
from sqlalchemy.orm import joinedload

from models import Client, SubClient, Consultation, TranslationProject
from interpretation_models import InterpretationProject
from annotation_models import AnnotationProject
from recruitment_models import RecruitmentProject
from workflow_models import ProjectWorkbenchResponsibility
from project_client_manager import ProjectClientManagerChange
from project_arrangement import ProjectArrangement, ready
from search_matching import keyword_any

MODELS = {'translation': TranslationProject, 'interpretation': InterpretationProject,
          'annotation': AnnotationProject, 'recruitment': RecruitmentProject,
          'assigned_translation': TranslationProject}
LABELS = {'translation': '笔译项目', 'interpretation': '口译项目', 'annotation': '标注项目',
          'recruitment': '招聘项目', 'assigned_translation': '被安排笔译类项目'}


def search(db, user, group, keyword='', page=1, page_size=10):
    if group not in MODELS:
        raise HTTPException(422, '请选择有效项目分类')
    model = MODELS[group]
    query = db.query(model).outerjoin(Client, model.client_id == Client.id).outerjoin(
        SubClient, model.sub_client_id == SubClient.id).outerjoin(Consultation, model.consultation_id == Consultation.id)
    query = query.options(joinedload(model.client), joinedload(model.sub_client))
    if group == 'assigned_translation':
        if not ready(db):
            return {'items': [], 'total': 0, 'ready': False}
        own = exists().where(ProjectArrangement.project_id == model.id, ProjectArrangement.assignee_id == user.id)
    else:
        if group == 'translation':
            manager = model.project_manager_id == user.id
        else:
            role = ProjectWorkbenchResponsibility
            manager = exists().where(getattr(role, group + '_project_id') == model.id,
                                     role.role_code == 'project_manager', role.assignee_id == user.id)
        if group in ('annotation', 'recruitment'):
            client_manager = model.client_manager_id == user.id
        else:
            change = ProjectClientManagerChange
            latest = select(change.new_manager_id).where(change.project_type == group, change.project_id == model.id).order_by(change.revision.desc()).limit(1).correlate(model).scalar_subquery()
            changed = exists().where(change.project_type == group, change.project_id == model.id)
            legacy = case((model.sub_client_id.is_not(None), SubClient.client_manager), else_=Client.client_manager)
            names = [value.strip().lower() for value in [user.username, user.full_name] if value and value.strip()]
            client_manager = case((changed, latest == user.id),
                                  (Consultation.customer_service_id.is_not(None), Consultation.customer_service_id == user.id),
                                  else_=func.lower(func.trim(legacy)).in_(names))
        own = or_(manager, client_manager)
    query = query.filter(own)
    fields = [model.order_no, model.project_name, Client.client_name, Client.client_short_name, SubClient.client_name, SubClient.client_short_name]
    if model is TranslationProject:
        fields.append(model.source_file_name)
    query = query.filter(keyword_any(fields, keyword))
    total = query.count()
    rows = query.order_by(model.order_no.desc(), model.id).offset((page - 1) * page_size).limit(page_size).all()
    project_type = 'translation' if group == 'assigned_translation' else group
    items = []
    for row in rows:
        client = row.sub_client or row.client
        items.append({'id': str(row.id), 'project_id': str(row.id), 'project_type': project_type,
                      'order_no': row.order_no, 'project_name': getattr(row, 'source_file_name', None) or row.project_name or '-',
                      'client_short_name': (client.client_short_name or client.client_name) if client else '-',
                      'project_status': row.project_status or '-'})
    return {'ready': True, 'total': total, 'items': items}
