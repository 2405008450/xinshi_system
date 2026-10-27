"""取消及回执只使用内存隔离库。"""
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from test_resource_request_dispatch import setup_data
from test_chat_participant_access import environment  # noqa: F401


def test_circle_cancel_is_independent_preserves_history_and_acknowledges_once(environment, monkeypatch):
    db, sender, receiver, outsider, request, project, service, notices = setup_data(environment, monkeypatch)
    from resource_request_cancellation import cancel_kind
    from resource_request_send_history import history
    from resource_request_dispatch_models import ResourceRequestDispatch as Batch
    circle = service.send(db, sender, request.id, service.DispatchWrite(kind='circle', user_ids=[receiver.id], idempotency_key=str(uuid4())))
    post = service.send(db, sender, request.id, service.DispatchWrite(kind='post', user_ids=[receiver.id], idempotency_key=str(uuid4())))
    service.receipt(db, receiver, UUID(circle['id']), 'received')
    assert cancel_kind(db, sender, request.id, 'circle')['cancelled_count'] == 1
    assert cancel_kind(db, sender, request.id, 'circle')['cancelled_count'] == 0
    cancelled = service.detail(db, receiver, UUID(circle['id']))
    assert cancelled['can_respond'] is False
    assert cancelled['recipients'][0]['received_at'] is not None
    assert cancelled['snapshot'] == circle['snapshot']
    notice_id = UUID(cancelled['cancellation']['id'])
    assert service.detail(db, receiver, notice_id)['is_cancellation'] is True
    assert service.detail(db, receiver, UUID(post['id']))['cancellation'] is None
    assert request.demand_status == 'draft'
    with pytest.raises(HTTPException):
        service.receipt(db, receiver, UUID(circle['id']), 'processed')
    with pytest.raises(HTTPException):
        service.receipt(db, outsider, notice_id, 'cancel_received')
    with pytest.raises(HTTPException):
        service.receipt(db, receiver, notice_id, 'processed')
    before = len(notices)
    for _ in range(2):
        result = service.receipt(db, receiver, notice_id, 'cancel_received')
    assert len(notices) == before + 1 and notices[-1][0] == [sender.id]
    assert '确认收到取消通知' in notices[-1][1]
    assert result['cancellation']['confirmed_count'] == 1
    assert result['cancellation']['recipients'][0]['confirmed_at'].endswith('+08:00')
    record = history(db, request.id)['records']['circle'][0]
    assert record['cancellation']['confirmed_count'] == 1
    assert len(history(db, request.id)['records']['circle']) == 1
    assert db.query(Batch).count() == 3


def test_development_cancel_sets_status_notifies_all_batches_and_routes_receipts_to_canceller(environment, monkeypatch):
    db, sender, receiver, outsider, request, project, service, notices = setup_data(environment, monkeypatch)
    from resource_request_service import send_resource_request, cancel_resource_request
    from resource_request_send_history import history
    from resource_request_dispatch_models import ResourceRequestDispatch as Batch
    for _ in range(2):
        send_resource_request(db, request.id, sender.id, str(uuid4()), [receiver.id])
    result = cancel_resource_request(db, request.id, outsider.id)
    assert result['demand_status'] == result['request_status'] == 'cancelled'
    cancellations = db.query(Batch).filter_by(kind='cancellation').all()
    assert len(cancellations) == 2
    assert all(row.sender_id == outsider.id for row in cancellations)
    original_count = len(notices)
    cancel_resource_request(db, request.id, outsider.id)
    assert len(notices) == original_count
    service.receipt(db, receiver, cancellations[0].id, 'cancel_received')
    assert notices[-1][0] == [outsider.id]
    assert all(row['cancellation'] for row in history(db, request.id)['records']['development'])


def test_cancelled_post_rejects_execution_and_new_send_is_independent(environment, monkeypatch):
    db, sender, receiver, outsider, request, project, service, notices = setup_data(environment, monkeypatch)
    from resource_request_cancellation import cancel_kind
    from resource_request_execution import send, ExecutionWrite
    payload = service.DispatchWrite(kind='post', user_ids=[receiver.id], idempotency_key=str(uuid4()))
    original = service.send(db, sender, request.id, payload)
    cancel_kind(db, sender, request.id, 'post')
    with pytest.raises(HTTPException) as failure:
        send(db, receiver, UUID(original['id']), ExecutionWrite(platform_ids=[uuid4()], content='执行', idempotency_key=str(uuid4())))
    assert failure.value.status_code == 409
    fresh = service.send(db, sender, request.id, payload.model_copy(update={'idempotency_key': str(uuid4())}))
    assert fresh['cancellation'] is None and fresh['can_respond'] is False  # 发送人非接收人
    assert service.detail(db, receiver, UUID(fresh['id']))['can_respond'] is True


def test_cancel_endpoint_requires_project_write(environment, monkeypatch):
    db, sender, receiver, outsider, request, project, service, notices = setup_data(environment, monkeypatch)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.resource_requests import router
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: receiver
    assert TestClient(app).post(f'/resource-requests/{request.id}/dispatch/circle/cancel').status_code == 403


@pytest.fixture
def notification_ids():
    # 内存库不含生产库的 server_default，补齐通知主键与未读默认值。
    from sqlalchemy import event
    from models import AppNotification
    def assign(_mapper, _connection, target):
        if target.id is None:
            target.id = uuid4()
        if target.is_read is None:
            target.is_read = False
    event.listen(AppNotification, 'before_insert', assign)
    yield
    event.remove(AppNotification, 'before_insert', assign)


def test_cancellation_and_confirmation_persist_real_notifications_once(environment, monkeypatch, notification_ids):
    from resource_request_dispatch import publish as real_publish
    db, sender, receiver, outsider, request, project, service, notices = setup_data(environment, monkeypatch)
    monkeypatch.setattr(service, 'publish', real_publish)
    pushed = []
    monkeypatch.setattr('notification_ws.dispatch_personal_message', lambda uid, message: pushed.append((uid, message)))
    from resource_request_cancellation import cancel_kind
    from models import AppNotification
    batch = service.send(db, sender, request.id, service.DispatchWrite(kind='circle', user_ids=[receiver.id], idempotency_key=str(uuid4())))
    cancel_kind(db, outsider, request.id, 'circle')
    cancel_kind(db, outsider, request.id, 'circle')
    detail = service.detail(db, receiver, UUID(batch['id']))
    cancel_id = UUID(detail['cancellation']['id'])
    for _ in range(2):
        service.receipt(db, receiver, cancel_id, 'cancel_received')
    notifications = db.query(AppNotification).all()
    assert len(notifications) == len(pushed) == 3
    cancellation = next(row for row in notifications if '取消通知，请确认收到' in row.title)
    confirmation = next(row for row in notifications if '确认收到取消通知' in row.title)
    assert cancellation.recipient_user_id == receiver.id
    assert confirmation.recipient_user_id == outsider.id
    assert confirmation.related_entity_id == cancellation.related_entity_id == cancel_id
