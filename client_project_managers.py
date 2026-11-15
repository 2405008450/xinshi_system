"""客户列表的业务经理来自新咨询和项目，不读取客户联系人的姓名。"""

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select

from annotation_models import AnnotationProject
from annotation_progress_time import business_datetime
from interpretation_models import InterpretationProject
from models import AppUser, Consultation, SubClient, TranslationProject
from project_client_manager import ProjectClientManagerChange
from recruitment_models import RecruitmentProject


PROJECT_TYPES = (
    ('translation', '笔译项目', TranslationProject),
    ('interpretation', '口译项目', InterpretationProject),
    ('annotation', '标注项目', AnnotationProject),
    ('recruitment', '招聘项目', RecruitmentProject),
)


def manager_identity(manager_id, name):
    name = name.strip()
    return {'key': str(manager_id) if manager_id else f'name:{name}', 'name': name}


def client_rows(db, model, client_ids, *columns):
    return db.query(model.client_id, SubClient.parent_client_id, *columns).outerjoin(
        SubClient, SubClient.id == model.sub_client_id,
    ).filter(or_(model.client_id.in_(client_ids), SubClient.parent_client_id.in_(client_ids)))


def matching_clients(row, client_ids):
    return {row.client_id, row.parent_client_id} & client_ids


def project_rows(db, module, model, client_ids, *, manager_key=None):
    if module in ('translation', 'interpretation'):
        change = ProjectClientManagerChange
        latest = select(change.id).where(
            change.project_type == module, change.project_id == model.id,
        ).order_by(change.revision.desc()).limit(1).correlate(model).scalar_subquery()
        manager_id, manager_name = change.new_manager_id, change.new_manager_name
    else:
        manager_id = model.client_manager_id
        manager_name = func.coalesce(func.nullif(AppUser.full_name, ''), AppUser.username)
        if module == 'recruitment':
            manager_name = func.coalesce(manager_name, model.client_manager_name_snapshot)

    columns = [model.id, model.created_at, manager_id.label('manager_id'), manager_name.label('manager_name')]
    if manager_key is not None:
        columns.extend((model.order_no, model.project_name, model.project_status))
    query = client_rows(db, model, client_ids, *columns)
    if module in ('translation', 'interpretation'):
        query = query.join(change, change.id == latest)
    else:
        query = query.outerjoin(AppUser, AppUser.id == manager_id)
    if module == 'translation':
        query = query.filter(model.annotation_migrated_at.is_(None))
    if manager_key is not None:
        if manager_key.startswith('name:'):
            query = query.filter(manager_id.is_(None), func.trim(manager_name) == manager_key[5:])
        else:
            query = query.filter(manager_id == UUID(manager_key))
    return query.filter(func.trim(manager_name) != '')


def attach_client_project_managers(db, clients, *, read_consultations, read_projects):
    client_ids = {client.id for client in clients}
    if not client_ids:
        return

    managers = defaultdict(dict)
    if read_consultations:
        name = func.coalesce(func.nullif(AppUser.full_name, ''), AppUser.username)
        consultations = client_rows(
            db, Consultation, client_ids, Consultation.customer_service_id, name.label('manager_name'),
        ).join(AppUser, AppUser.id == Consultation.customer_service_id).filter(
            func.trim(name) != '',
        ).order_by(
            func.coalesce(Consultation.consultation_time, Consultation.created_at).asc().nulls_last(),
            Consultation.created_at.asc().nulls_last(), Consultation.id,
        )
        for row in consultations:
            manager = manager_identity(row.customer_service_id, row.manager_name)
            for client_id in matching_clients(row, client_ids):
                if not managers[client_id]:
                    managers[client_id][manager['key']] = manager

    if read_projects:
        projects = [
            (module, row)
            for module, _, model in PROJECT_TYPES
            for row in project_rows(db, module, model, client_ids)
        ]
        projects.sort(key=lambda item: (
            business_datetime(item[1].created_at or datetime.max), item[0], item[1].id,
        ))
        for _, row in projects:
            manager = manager_identity(row.manager_id, row.manager_name)
            for client_id in matching_clients(row, client_ids):
                managers[client_id].setdefault(manager['key'], manager)

    for client in clients:
        client.project_managers = list(managers[client.id].values())


def client_manager_project_groups(db, client_id, manager_key):
    groups = []
    for module, label, model in PROJECT_TYPES:
        query = project_rows(db, module, model, {client_id}, manager_key=manager_key)
        items = [
            {'id': str(row.id), 'order_no': row.order_no,
             'project_name': row.project_name, 'project_status': row.project_status}
            for row in query.order_by(model.order_no.desc(), model.id.desc())
        ]
        if items:
            groups.append({'module': module, 'label': label, 'items': items})
    return {'groups': groups}
