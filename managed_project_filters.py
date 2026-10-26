"""会话内“我的项目”筛选，复用列表与总数查询，不改变原有访问权限。"""
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import case, exists, or_, select


def apply_managed_filter(query, module, filters):
    descriptor = (filters or {}).get('managed_user_id')
    if not descriptor:
        return query
    try:
        ids = [UUID(str(value)) for value in descriptor.get('value', [])]
    except (ValueError, TypeError, AttributeError) as error:
        raise HTTPException(422, '负责人账号 ID 无效') from error
    from models import AppUser, Client, SubClient, TranslationProject, Consultation
    from workflow_models import ProjectWorkbenchResponsibility
    names = select(AppUser.full_name).where(AppUser.id.in_(ids), AppUser.full_name.is_not(None)).union(
        select(AppUser.username).where(AppUser.id.in_(ids)))
    if module == 'annotation':
        from annotation_models import AnnotationProject as Project
        managed = exists().where(ProjectWorkbenchResponsibility.annotation_project_id == Project.id,
                                 ProjectWorkbenchResponsibility.role_code == 'project_manager',
                                 ProjectWorkbenchResponsibility.assignee_id.in_(ids))
        return query.filter(or_(Project.client_manager_id.in_(ids), managed))
    if module == 'translation':
        Project = TranslationProject
        managed = Project.project_manager_id.in_(ids)
    elif module == 'interpretation':
        from interpretation_models import InterpretationProject as Project
        managed = exists().where(ProjectWorkbenchResponsibility.interpretation_project_id == Project.id,
                                 ProjectWorkbenchResponsibility.role_code == 'project_manager',
                                 ProjectWorkbenchResponsibility.assignee_id.in_(ids))
    else:
        Project = Consultation
        managed = or_(Project.customer_service_id.in_(ids), Project.sales_person_id.in_(ids), Project.follow_up_person_id.in_(ids))
    client_manager = case((Project.sub_client_id.is_not(None), SubClient.client_manager), else_=Client.client_manager)
    return query.filter(or_(managed, client_manager.in_(names)))
