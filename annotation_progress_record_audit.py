"""项目进度版本及删除留痕，复用项目审计表。"""
from fastapi import HTTPException
from datetime import datetime
from sqlalchemy import inspect
from annotation_progress_time import business_datetime
from project_audit_models import ProjectOperationAudit


def edit_audit_ready(db):
    if not hasattr(db, 'get_bind') or db.get_bind().dialect.name != 'postgresql':
        return True
    checks = inspect(db.connection()).get_check_constraints('project_operation_audit')
    return any(row['name'] == 'ck_project_operation_audit_operation' and 'progress_edit' in row['sqltext'] for row in checks)


def require_edit_audit_ready(db):
    if not edit_audit_ready(db):
        raise HTTPException(503, '进度编辑留痕尚未初始化，请管理员完成数据库同步后重试')


def record_snapshot(row):
    result = {key: getattr(row, key, None) for key in (
        'id', 'project_id', 'from_status', 'to_status', 'effective_on', 'changed_at',
        'changed_by', 'change_note', 'entry_kind', 'updated_at', 'updated_by',
    )}
    for key in ('effective_on', 'changed_at', 'updated_at'):
        if result[key] is not None:
            result[key] = business_datetime(result[key]).isoformat()
    return result


def project_record_audits(db, project_id):
    return db.query(ProjectOperationAudit).filter(
        ProjectOperationAudit.project_type == 'annotation',
        ProjectOperationAudit.project_id == project_id,
        ProjectOperationAudit.operation_source.in_(['progress_record_delete', 'progress_record_edit']),
    ).order_by(ProjectOperationAudit.occurred_at, ProjectOperationAudit.id).all()


def audit_response(row):
    snapshot = row.project_snapshot or {}
    def normalize_snapshot(value):
        if value is None:
            return None
        value = dict(value)
        for key in ('effective_on', 'changed_at', 'updated_at'):
            if value.get(key):
                time = datetime.fromisoformat(value[key]) if isinstance(value[key], str) else value[key]
                value[key] = business_datetime(time).isoformat()
        return value
    before = normalize_snapshot(snapshot.get('before_progress_record') or snapshot.get('deleted_progress_record') or {})
    return dict(id=row.id, record_id=before.get('id'), action='edit' if row.operation_type == 'progress_edit' else 'delete',
                actor_name=row.actor_name_snapshot or row.actor_username_snapshot or '系统',
                occurred_at=business_datetime(row.occurred_at), reason=row.change_reason,
                record_part=snapshot.get('record_part', 'progress'), before=before,
                after=normalize_snapshot(snapshot.get('after_progress_record')))


def include_deleted_records(db, project_id, records):
    """删除项保留在原时间轴；正文仅通过历史入口查看。"""
    indexed = {str(row['id']): row for row in records}
    for audit in project_record_audits(db, project_id):
        if audit.operation_type != 'progress_delete':
            continue
        snapshot = audit.project_snapshot or {}
        old = snapshot.get('deleted_progress_record') or {}
        key = str(old.get('id') or '')
        if not key:
            continue
        if snapshot.get('record_part') == 'status_note':
            if key in indexed and not indexed[key].get('change_note'):
                indexed[key]['note_deleted'] = True
        elif key not in indexed:
            indexed[key] = dict(old, project_id=project_id, is_deleted=True, change_note=None,
                                changed_by_name=None, entry_kind='progress')
    return list(indexed.values())
