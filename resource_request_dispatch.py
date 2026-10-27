"""授权接收人查看不可变需求快照，并向发送人回执；不发送站外消息。"""
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import inspect
from models import AppUser
from department_models import Department
from organization_service import department_condition
from resource_request_dispatch_models import ResourceRequestDispatch as Batch, ResourceRequestDispatchRecipient as Recipient
from resource_request_models import ResourceRequest
from chat_time import now

LABELS = {'circle': '发圈需求', 'post': '发帖需求', 'development': '资源需求管理'}


class DispatchWrite(BaseModel):
    kind: str
    user_ids: list[UUID] = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=16, max_length=128)


class ManagementSendWrite(BaseModel):
    user_ids: list[UUID] = Field(min_length=1, max_length=500)


class ReceiptWrite(BaseModel):
    status: str


def eligible(db,kind="circle"):
    from resource_request_dispatch_defaults import eligible as eligible_people
    return eligible_people(db,kind)


def options(db):
    return [dict(id=str(p.id), name=p.full_name or p.username) for p in eligible(db)]


def publish(db, users, title, batch):
    from crud import create_notifications_for_users
    project = batch.snapshot.get('current_project_name') or batch.snapshot.get('source_project_name_snapshot') or '未命名项目'
    notifications = create_notifications_for_users(db, users, f'{title} · {project}'[:200], f'项目：{project}\n需求编号：{batch.snapshot.get("request_no", "-")}\n点击查看完整需求及回执。', notification_type='resource_request_dispatch', related_project_type='resource_request_dispatch', related_entity_id=batch.id, commit=False)
    db.info.setdefault('resource_dispatch_notifications', []).extend(notifications)


def commit(db):
    notifications = db.info.pop('resource_dispatch_notifications', [])
    db.commit()
    from notification_ws import dispatch_personal_message
    from schemas import NotificationResponse
    for notice in notifications:
        dispatch_personal_message(notice.recipient_user_id, {'type':'notification', 'notification':NotificationResponse.model_validate(notice).model_dump(mode='json')})


def send(db, user, request_id, payload):
    if payload.kind not in {'circle', 'post'}:
        raise HTTPException(422, '不支持的发送类型')
    # 同一需求串行化发送，重复点击或请求重试只创建一个批次。
    request = db.query(ResourceRequest).filter_by(id=request_id).with_for_update().first()
    if not request or request.source_type != 'annotation':
        raise HTTPException(404, '标注资源需求不存在')
    ids = set(payload.user_ids)
    previous = db.query(Batch).filter_by(idempotency_key=payload.idempotency_key).first()
    if previous:
        targets = {uid for uid, in db.query(Recipient.user_id).filter_by(dispatch_id=previous.id)}
        if previous.sender_id != user.id or previous.request_id != request_id or previous.kind != payload.kind or targets != ids:
            raise HTTPException(409, '发送标识已被其他操作使用，请重新发送')
        return detail(db, user, previous.id)
    if not ids <= {p.id for p in eligible(db,payload.kind)}:
        raise HTTPException(422, '部分人员已不在标注项目部或已停用，请重新选择')
    from resource_request_send_history import assert_limit
    assert_limit(db, request_id, payload.kind)
    from resource_request_content import allocate_partial
    allocate_partial(db, request)
    db.flush()
    from resource_request_send_history import snapshot as request_snapshot
    snapshot = request_snapshot(db, request_id)
    batch = Batch(request_id=request_id, sender_id=user.id, kind=payload.kind, idempotency_key=payload.idempotency_key, snapshot=snapshot)
    db.add(batch); db.flush()
    db.add_all([Recipient(dispatch_id=batch.id, user_id=uid) for uid in ids])
    publish(db, list(ids), LABELS[batch.kind], batch)
    commit(db)
    return detail(db, user, batch.id)


def detail(db, user, batch_id):
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, '需求通知不存在')
    recipient = db.get(Recipient, (batch.id, user.id))
    if batch.sender_id != user.id and not recipient:
        raise HTTPException(404, '需求通知不存在')
    users = {p.id:p for p in db.query(AppUser).join(Recipient, Recipient.user_id==AppUser.id).filter(Recipient.dispatch_id==batch.id)}
    from business_time import BUSINESS_TIMEZONE
    stamp = lambda value: value.replace(tzinfo=BUSINESS_TIMEZONE).isoformat() if value and value.tzinfo is None else value.astimezone(BUSINESS_TIMEZONE).isoformat() if value else None
    from resource_request_execution import replies
    from resource_request_cancellation import summary
    cancelled = summary(db, batch)
    kind = batch.snapshot.get('cancelled_kind') if batch.kind == 'cancellation' else batch.kind
    return dict(id=str(batch.id), kind=kind, label=LABELS.get(kind, '需求') + (' · 取消通知' if batch.kind == 'cancellation' else ''), snapshot=batch.snapshot, execution_replies=replies(db,[batch.id]) if batch.kind=="post" else [], is_sender=batch.sender_id==user.id,
        is_cancellation=batch.kind=='cancellation', cancellation=cancelled,
        can_respond=recipient is not None and (batch.kind=='cancellation' or not cancelled), created_at=stamp(batch.created_at), recipients=[dict(user_id=str(r.user_id), name=users[r.user_id].full_name or users[r.user_id].username, received_at=stamp(r.received_at), processed_at=stamp(r.processed_at)) for r in db.query(Recipient).filter_by(dispatch_id=batch.id)])


def receipt(db, user, batch_id, status):
    if status not in {'received', 'processed', 'cancel_received'}:
        raise HTTPException(422, '不支持的回执状态')
    batch = db.get(Batch, batch_id)
    from resource_request_cancellation import lock_request, assert_active
    if batch:
        lock_request(db, batch.request_id)
    recipient = db.query(Recipient).filter_by(dispatch_id=batch_id, user_id=user.id).populate_existing().with_for_update().first()
    if not batch or not recipient:
        raise HTTPException(404, '你不是该需求的接收人')
    if batch.kind == 'cancellation':
        if status != 'cancel_received':
            raise HTTPException(422, '请确认收到取消通知')
        if not recipient.received_at:
            recipient.received_at = now()
            publish(db, [batch.sender_id], f'{user.full_name or user.username} · 确认收到取消通知 · {LABELS[batch.snapshot["cancelled_kind"]]}', batch)
            commit(db)
        return detail(db, user, batch_id)
    if status == 'cancel_received':
        raise HTTPException(422, '该通知不是取消通知')
    assert_active(db, batch)
    if batch.kind == 'post' and status == 'processed':
        from resource_request_dispatch_models import ResourceRequestExecutionReply
        if not db.query(ResourceRequestExecutionReply.id).filter_by(dispatch_id=batch_id, user_id=user.id).first():
            raise HTTPException(409, '请先选择实际发布的平台并填写处理说明，提交执行回执后自动标记已处理')
    field = 'received_at' if status=='received' else 'processed_at'
    if not getattr(recipient, field):
        if status=='processed' and not recipient.received_at:
            raise HTTPException(409, '请先点击已收到，再确认已处理')
        setattr(recipient, field, now())
        publish(db, [batch.sender_id], f'{user.full_name or user.username} · {"已收到" if status=="received" else "已处理"} · {LABELS[batch.kind]}', batch)
        commit(db)
    return detail(db, user, batch_id)


def annotate_sender_entries(db, user_id, notifications):
    ids = {row.related_entity_id for row in notifications if row.notification_type == 'resource_request_dispatch' and row.related_entity_id}
    owned = {row[0] for row in db.query(Batch.id).filter(Batch.id.in_(ids), Batch.sender_id == user_id)} if ids else set()
    for row in notifications:
        row.can_open_resource_request = row.notification_type == 'resource_request_dispatch' and row.related_entity_id in owned


def sender_request(db, user, batch_id):
    batch = db.get(Batch, batch_id)
    if not batch or batch.sender_id != user.id:
        raise HTTPException(404, '该入口仅限需求发送人')
    from resource_request_service import get_resource_request
    request = get_resource_request(db, batch.request_id)
    if not request:
        raise HTTPException(404, '资源需求不存在')
    return request
