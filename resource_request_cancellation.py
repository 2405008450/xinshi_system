"""取消作为独立通知批次保存，保留原需求快照及原收到／处理回执。"""
from fastapi import HTTPException
from resource_request_dispatch_models import ResourceRequestDispatch as Batch, ResourceRequestDispatchRecipient as Recipient


def cancellation(db, batch_id):
    return db.query(Batch).filter_by(idempotency_key=f'cancel-dispatch:{batch_id}', kind='cancellation').first()


def cancel_batches(db, request_id, kind, actor_id):
    from resource_request_dispatch import publish, LABELS
    if kind not in LABELS:
        raise HTTPException(422, '不支持的取消类型')
    # 调用方先锁定需求，所有发送、取消和执行回执遵循同一把需求锁。
    originals = db.query(Batch).filter_by(request_id=request_id, kind=kind).order_by(Batch.created_at, Batch.id).all()
    count = 0
    for original in originals:
        if cancellation(db, original.id):
            continue
        targets = [uid for uid, in db.query(Recipient.user_id).filter_by(dispatch_id=original.id)]
        notice = Batch(request_id=request_id, sender_id=actor_id, kind='cancellation',
                       idempotency_key=f'cancel-dispatch:{original.id}',
                       snapshot={**original.snapshot, 'cancelled_kind': kind, 'original_dispatch_id': str(original.id)})
        db.add(notice); db.flush()
        db.add_all([Recipient(dispatch_id=notice.id, user_id=uid) for uid in targets])
        if targets:
            publish(db, targets, f'{LABELS[kind]} · 取消通知，请确认收到', notice)
        count += 1
    return count


def lock_request(db, request_id):
    from resource_request_models import ResourceRequest
    return db.query(ResourceRequest).filter_by(id=request_id).populate_existing().with_for_update().first()


def assert_active(db, batch):
    if cancellation(db, batch.id):
        raise HTTPException(409, '该需求通知已取消，请查看取消通知并确认收到')


def cancel_kind(db, user, request_id, kind):
    if kind not in {'circle', 'post'}:
        raise HTTPException(422, '请使用取消需求入口取消资源开拓需求')
    request = lock_request(db, request_id)
    if not request or request.source_type != 'annotation':
        raise HTTPException(404, '标注资源需求不存在')
    count = cancel_batches(db, request_id, kind, user.id)
    from resource_request_dispatch import commit
    commit(db)
    return {'cancelled_count': count}


def summary(db, batch):
    notice = batch if batch.kind == 'cancellation' else cancellation(db, batch.id)
    if not notice:
        return None
    from resource_request_send_history import stamp
    from models import AppUser
    actor = db.get(AppUser, notice.sender_id)
    receipts = db.query(Recipient).filter_by(dispatch_id=notice.id).all()
    names = {p.id: p.full_name or p.username for p in db.query(AppUser).filter(AppUser.id.in_([r.user_id for r in receipts]))} if receipts else {}
    return dict(id=str(notice.id), cancelled_at=stamp(notice.created_at), cancelled_by=actor.full_name or actor.username if actor else '历史人员',
                confirmed_count=sum(bool(r.received_at) for r in receipts), recipients=[dict(user_id=str(r.user_id), name=names.get(r.user_id, '历史人员'), confirmed_at=stamp(r.received_at)) for r in receipts])
