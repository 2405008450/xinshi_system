"""项目会话的日期/状态视图共用来源；负责人筛选不能授予额外会话权限。"""
from uuid import UUID
from sqlalchemy import and_, false, func, inspect, or_, select
from models import TranslationProject, Client, SubClient
from annotation_models import AnnotationProject
from interpretation_models import InterpretationProject
from recruitment_models import RecruitmentProject

MODELS = {'annotation': AnnotationProject, 'translation': TranslationProject,
          'interpretation': InterpretationProject, 'recruitment': RecruitmentProject}


def mine_condition(db, kind, model, user):
    conditions = []
    if hasattr(model, 'client_manager_id'):
        conditions.append(model.client_manager_id == user.id)
    if kind == 'translation':
        conditions.append(model.project_manager_id == user.id)
    else:
        from workflow_models import ProjectWorkbenchResponsibility as Role
        column = getattr(Role, f'{kind}_project_id')
        conditions.append(model.id.in_(select(column).where(Role.role_code == 'project_manager', Role.assignee_id == user.id)))
    if kind in ('translation', 'interpretation'):
        from project_client_manager import manager_self_expression, ProjectClientManagerChange
        names = [name.strip().lower() for name in (user.full_name, user.username) if name and name.strip()]
        fallback = func.coalesce(
            select(SubClient.client_manager).where(SubClient.id == model.sub_client_id).correlate(model).scalar_subquery(),
            select(Client.client_manager).where(Client.id == model.client_id).correlate(model).scalar_subquery())
        if inspect(db.connection()).has_table(ProjectClientManagerChange.__tablename__):
            conditions.append(manager_self_expression(kind, model.id, user.id, names, fallback))
        else:
            conditions.append(func.lower(func.trim(fallback)).in_(names))
    return or_(*conditions) if conditions else false()


def discussion_sources(db, room_ids):
    if not room_ids:
        return {}
    ids = [UUID(str(value)) for value in room_ids]
    inspector = inspect(db.connection())
    result = {}
    from project_delivery import ProjectChatDispatch
    from translation_chat_delivery import TranslationProjectConversation
    from technical_requirement_models import TechnicalRoom
    if inspector.has_table(ProjectChatDispatch.__tablename__):
        for room_id, kind, project_id in db.query(ProjectChatDispatch.room_id, ProjectChatDispatch.module, ProjectChatDispatch.project_id).filter(ProjectChatDispatch.room_id.in_(ids)):
            result[str(room_id)] = (kind, project_id)
    for model, kind in ((TranslationProjectConversation, 'translation'), (TechnicalRoom, 'annotation')):
        if inspector.has_table(model.__tablename__):
            for room_id, project_id in db.query(model.room_id, model.project_id).filter(model.room_id.in_(ids)):
                result[str(room_id)] = (kind, project_id)
    return result


def work_report_context(db, user, kind, conversation_id):
    from chat_message_interactions import scope
    scope(db, kind, conversation_id, user)
    source = discussion_sources(db, [conversation_id]).get(str(conversation_id)) if kind == 'discussion' else (kind, conversation_id)
    if not source or source[0] not in MODELS:
        return dict(project=None)
    module, project_id = source
    project = db.get(MODELS[module], project_id)
    return dict(project=dict(id=str(project.id), type=module, name=project.project_name or project.order_no,
                             order_no=project.order_no) if project else None)


def owned_discussion_ids(db, user, room_ids):
    sources = discussion_sources(db, room_ids)
    owned = set()
    for kind, model in MODELS.items():
        ids = {pid for source_kind, pid in sources.values() if source_kind == kind}
        if ids:
            owned.update((kind, pid) for pid, in db.query(model.id).filter(model.id.in_(ids), mine_condition(db, kind, model, user)))
    return {room_id for room_id, source in sources.items() if source in owned}


def decorate_sessions(db, user, rows):
    sources = discussion_sources(db, [row['project_id'] for row in rows if row['kind'] == 'discussion'])
    for row in rows:
        if row['kind'] in MODELS:
            sources[row['key']] = (row['kind'], UUID(str(row['project_id'])))
    metadata = {}
    for kind, model in MODELS.items():
        ids = {pid for source_kind, pid in sources.values() if source_kind == kind}
        if not ids:
            continue
        for pid, status, mine in db.query(model.id, model.project_status, mine_condition(db, kind, model, user)).filter(model.id.in_(ids)):
            metadata[(kind, pid)] = dict(project_module=kind, source_project_id=str(pid), project_status=status, is_my_project=bool(mine))
    for row in rows:
        source = sources.get(str(row['project_id'])) if row['kind'] == 'discussion' else sources.get(row['key'])
        row.update(metadata.get(source, dict(is_my_project=False)))
