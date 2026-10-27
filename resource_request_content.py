"""标注资源需求项目快照与分批语种发送规则。"""
from sqlalchemy import func
from fastapi import HTTPException
from models import AppUser
from annotation_models import AnnotationProject
from resource_request_models import ResourceRequest


def annotation_context(db, project_id):
    project = db.get(AnnotationProject, project_id)
    if not project:
        raise HTTPException(404, '标注项目不存在')
    managers = [dict(id=str(r['assignee_id']), name=r['assignee_name']) for r in project.role_assignments if r['role_code']=='project_manager' and r['assignee_id']]
    collapse = not project.parent_project_id and db.query(AnnotationProject.id).filter_by(parent_project_id=project.id).first() is not None
    return dict(project_managers=managers, collapse_languages=collapse)


def prepare_data(db, payload, data, existing=None):
    # 旧客户端只提交需求版本时，不清空已保存的三类说明；显式空串仍可清空。
    if 'request_content' in data:
        previous_notes = ((existing.request_content or {}).get('dispatch_notes') or {}) if existing else {}
        submitted_notes = payload.request_content.dispatch_notes.model_dump(exclude_unset=True)
        data['request_content']['dispatch_notes'] = {**previous_notes, **submitted_notes}
    if payload.source_type != 'annotation':
        if payload.partial_requested:
            raise HTTPException(422, '仅标注母订单可发送部分语种需求')
        return data
    context = annotation_context(db, payload.annotation_project_id)
    data['owner_id'] = context['project_managers'][0]['id'] if context['project_managers'] else None
    if data['owner_id']:
        from uuid import UUID
        data['owner_id'] = UUID(data['owner_id'])
    if payload.partial_requested and not context['collapse_languages']:
        raise HTTPException(422, '仅存在子订单的标注母订单可标记部分语种')
    if existing and existing.partial_sequence:
        # 已发送的批次标题和标记不得被后续编辑或项目同步抹掉。
        data['partial_requested'] = True
        data['source_project_name_snapshot'] = existing.source_project_name_snapshot
    return data


def allocate_partial(db, row):
    if not row.partial_requested or row.partial_sequence:
        return
    if not row.items:
        raise HTTPException(422, '部分语种需求至少保留一条语种明细')
    project = db.query(AnnotationProject).filter_by(id=row.annotation_project_id).with_for_update().one()
    number = (db.query(func.max(ResourceRequest.partial_sequence)).filter_by(annotation_project_id=project.id).scalar() or 0) + 1
    row.partial_sequence = number
    row.source_project_name_snapshot = f'部分语种（{number}）{project.project_name or project.order_no}'


def display_name(row, name):
    return row.source_project_name_snapshot if row.partial_sequence else name
