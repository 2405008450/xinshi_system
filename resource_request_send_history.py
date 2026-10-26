"""三条发送路径各自计数，沿用现有批次表和进度日志，不补造历史记录。"""
from uuid import uuid4
from datetime import datetime
from fastapi import HTTPException
from models import AppUser
from resource_request_models import ResourceRequest, ResourceRequestProgressLog
from resource_request_dispatch_models import ResourceRequestDispatch as Batch, ResourceRequestDispatchRecipient as Recipient
from business_time import BUSINESS_TIMEZONE

LIMIT = 5
DEVELOPMENT_NOTE = '资源需求已发送'


def stamp(value):
    if not value:
        return None
    return (value.astimezone(BUSINESS_TIMEZONE) if value.tzinfo else value.replace(tzinfo=BUSINESS_TIMEZONE)).isoformat()


def management_logs(db, request_id):
    return db.query(ResourceRequestProgressLog).filter_by(request_id=request_id, progress_note=DEVELOPMENT_NOTE).order_by(ResourceRequestProgressLog.changed_at, ResourceRequestProgressLog.id).all()


def assert_limit(db, request_id, kind):
    count = len(management_logs(db, request_id)) if kind == 'development' else db.query(Batch).filter_by(request_id=request_id, kind=kind).count()
    if count >= LIMIT:
        raise HTTPException(409, '该发送方式已发送5次，不能再次发送')
    return count + 1


def snapshot(db, request_id):
    from resource_request_service import get_resource_request
    from resource_request_schemas import ResourceRequestResponse
    value = ResourceRequestResponse.model_validate(get_resource_request(db, request_id)).model_dump(mode='json')
    for field in ['requested_at', 'created_at', 'updated_at', 'completed_at']:
        if value.get(field):
            value[field] = stamp(datetime.fromisoformat(value[field]))
    return value


def history(db, request_id):
    if not db.get(ResourceRequest, request_id):
        raise HTTPException(404, '资源需求不存在')
    batches = db.query(Batch).filter_by(request_id=request_id).order_by(Batch.created_at, Batch.id).all()
    recipients = db.query(Recipient).filter(Recipient.dispatch_id.in_([row.id for row in batches])).all() if batches else []
    logs = management_logs(db, request_id)
    ids = {row.sender_id for row in batches} | {row.user_id for row in recipients} | {row.changed_by for row in logs if row.changed_by}
    names = {row.id: row.full_name or row.username for row in db.query(AppUser).filter(AppUser.id.in_(ids))} if ids else {}
    result = {kind: [] for kind in ['circle', 'post', 'development']}
    for batch in batches:
        if batch.kind not in ['circle', 'post']:
            continue
        targets = [row for row in recipients if row.dispatch_id == batch.id]
        result[batch.kind].append(dict(id=str(batch.id), number=len(result[batch.kind]) + 1, sender_name=names.get(batch.sender_id, '历史人员'), sent_at=stamp(batch.created_at), recipients=[names.get(row.user_id, '历史人员') for row in targets], received_count=sum(bool(row.received_at) for row in targets), processed_count=sum(bool(row.processed_at) for row in targets)))
    for log in logs:
        batch = next((b for b in batches if b.kind == 'development' and b.snapshot.get('send_log_id') == str(log.id)), None)
        targets = [r for r in recipients if batch and r.dispatch_id == batch.id]
        result['development'].append(dict(id=str(log.id), number=len(result['development']) + 1, sender_name=names.get(log.changed_by, '历史人员'), sent_at=stamp(log.changed_at), recipients=[names.get(r.user_id, '历史人员') for r in targets], received_count=sum(bool(r.received_at) for r in targets), processed_count=sum(bool(r.processed_at) for r in targets)))
    from resource_request_execution import replies
    executions=replies(db,[b.id for b in batches if b.kind=='post'])
    for record in result['post']:
        record['execution_replies']=[r for r in executions if r['dispatch_id']==record['id']]
    return dict(limit=LIMIT, records=result)
