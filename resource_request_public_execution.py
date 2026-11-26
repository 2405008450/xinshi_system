"""公众号先执行、后通知全体；复用通知批次与执行回执表，不改写历史快照。"""
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, Field
from models import AppUser
from resource_request_dispatch_models import (
    ResourceRequestDispatch as Batch, ResourceRequestDispatchRecipient as Recipient,
    ResourceRequestExecutionReply as Reply,
)
from resource_request_dispatch_kinds import PUBLIC_BROADCAST_KIND, LABELS
from resource_request_send_history import stamp
from business_time import business_now


class PublicExecutionWrite(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    idempotency_key: str = Field(min_length=16, max_length=128)


def broadcast(db, batch):
    return db.query(Batch).filter_by(
        kind=PUBLIC_BROADCAST_KIND, idempotency_key=f'public-broadcast:{batch.id}'
    ).first()


def broadcast_summary(db, batch):
    if batch.kind != 'wechat_public':
        return None
    row = broadcast(db, batch)
    if not row:
        return None
    people = {p.id: p.full_name or p.username for p in db.query(AppUser).join(
        Recipient, Recipient.user_id == AppUser.id).filter(Recipient.dispatch_id == row.id)}
    return dict(id=str(row.id), sent_at=stamp(row.created_at), recipients=[
        dict(user_id=str(r.user_id), name=people.get(r.user_id, '历史人员'),
             received_at=stamp(r.received_at), processed_at=stamp(r.processed_at))
        for r in db.query(Recipient).filter_by(dispatch_id=row.id)
    ])


def execute(db, user, batch_id: UUID, payload: PublicExecutionWrite):
    from resource_request_cancellation import lock_request, assert_active
    from resource_request_dispatch import publish, commit, detail
    candidate = db.get(Batch, batch_id)
    if candidate:
        lock_request(db, candidate.request_id)
    recipient = db.get(Recipient, (batch_id, user.id))
    if not candidate or candidate.kind != 'wechat_public' or not candidate.snapshot.get('public_execution_workflow') or not recipient:
        raise HTTPException(404, '你不是该公众号需求的执行人')
    assert_active(db, candidate)
    content = payload.content.strip()
    if not content:
        raise HTTPException(422, '请填写公众号执行说明')
    previous = db.query(Reply).filter_by(idempotency_key=payload.idempotency_key).first()
    if previous:
        if previous.dispatch_id != batch_id or previous.user_id != user.id or previous.content != content:
            raise HTTPException(409, '回复标识已用于其他操作，请重新回复')
        return detail(db, user, batch_id)
    if not recipient.received_at:
        raise HTTPException(409, '请先确认已收到，再填写公众号执行说明')
    db.add(Reply(dispatch_id=batch_id, user_id=user.id, platforms=[], content=content,
                 idempotency_key=payload.idempotency_key))
    recipient.processed_at = business_now()
    publish(db, [candidate.sender_id], f'{user.full_name or user.username} · 公众号执行说明', candidate)
    # 同一需求锁保证两位执行人同时提交或重试时，全体只收到一批通知。
    if not broadcast(db, candidate):
        targets = [p.id for p in db.query(AppUser).filter(
            AppUser.is_active.is_(True), AppUser.is_deleted.is_(False))]
        row = Batch(request_id=candidate.request_id, sender_id=candidate.sender_id,
                    kind=PUBLIC_BROADCAST_KIND, idempotency_key=f'public-broadcast:{batch_id}',
                    snapshot={**candidate.snapshot, 'original_dispatch_id': str(batch_id),
                              'public_execution_content': content,
                              'public_executed_by': user.full_name or user.username})
        db.add(row)
        db.flush()
        db.add_all([Recipient(dispatch_id=row.id, user_id=uid) for uid in targets])
        publish(db, targets, LABELS[PUBLIC_BROADCAST_KIND], row)
    commit(db)
    return detail(db, user, batch_id)
