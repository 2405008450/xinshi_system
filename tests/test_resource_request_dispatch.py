from uuid import uuid4
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment  # noqa: F401


def setup_data(environment, monkeypatch):
    from resource_request_models import ResourceRequest
    from annotation_models import AnnotationProject
    from department_models import Department, DepartmentMember
    import resource_request_dispatch as service
    db, (sender, receiver, outsider) = environment
    department = Department(id=uuid4(), name='标注项目部')
    project = AnnotationProject(id=uuid4(), order_no='AP-261023-TEST', project_name='隔离需求测试', created_by=sender.id)
    db.add_all([department, project]); db.flush()
    db.add(DepartmentMember(department_id=department.id, user_id=receiver.id, position='项目助理'))
    request = ResourceRequest(id=uuid4(), request_no='RR-TEST', source_type='annotation', request_category='annotation_trial', annotation_project_id=project.id, source_project_name_snapshot=project.project_name, source_project_types_snapshot=[], request_detail='总体需求', request_content={'versions':[{'name':'发帖','content':'发帖正文'}]}, partial_requested=False, partial_sequence=0, progress_percent=0, priority='medium', request_status='draft', demand_status='draft')
    db.add(request);db.commit()
    from business_time import business_now
    request.requested_at=request.created_at=request.updated_at=business_now()
    db.commit()
    notices=[]
    monkeypatch.setattr(service, 'publish', lambda db, ids, title, batch: notices.append((list(ids),title)))
    return db,sender,receiver,outsider,request,project,service,notices


def test_snapshot_recipients_permission_idempotency_and_receipt_order(environment, monkeypatch):
    db,sender,receiver,outsider,request,project,service,notices=setup_data(environment,monkeypatch)
    from resource_request_dispatch_models import ResourceRequestDispatch as Batch
    payload=service.DispatchWrite(kind='circle',user_ids=[receiver.id,receiver.id],idempotency_key=str(uuid4()))
    result=service.send(db,sender,request.id,payload)
    batch_id=__import__('uuid').UUID(result['id'])
    service.send(db,sender,request.id,payload)
    assert db.query(Batch).count()==1 and len(notices)==1
    assert result['snapshot']['request_detail']=='总体需求'
    request.request_detail='后续修改';db.commit()
    assert service.detail(db,receiver,batch_id)['snapshot']['request_detail']=='总体需求'
    with pytest.raises(HTTPException) as forbidden:service.detail(db,outsider,batch_id)
    assert forbidden.value.status_code==404
    with pytest.raises(HTTPException) as order:service.receipt(db,receiver,batch_id,'processed')
    assert order.value.status_code==409
    received=service.receipt(db,receiver,batch_id,'received')
    assert received['recipients'][0]['received_at'].endswith('+08:00')
    service.receipt(db,receiver,batch_id,'received')
    service.receipt(db,receiver,batch_id,'processed')
    service.receipt(db,receiver,batch_id,'processed')
    assert len(notices)==3 and notices[-1][0]==[sender.id]
    with pytest.raises(HTTPException):service.receipt(db,outsider,batch_id,'received')


def test_dispatch_requires_current_department_and_different_kinds_are_independent(environment, monkeypatch):
    db,sender,receiver,outsider,request,project,service,notices=setup_data(environment,monkeypatch)
    with pytest.raises(HTTPException):service.send(db,sender,request.id,service.DispatchWrite(kind='circle',user_ids=[outsider.id],idempotency_key=str(uuid4())))
    ids=[]
    for kind in ['circle','post']:
        result=service.send(db,sender,request.id,service.DispatchWrite(kind=kind,user_ids=[receiver.id],idempotency_key=str(uuid4())))
        ids.append(result['id'])
    assert ids[0]!=ids[1]
    first=__import__('uuid').UUID(ids[0]);second=__import__('uuid').UUID(ids[1])
    service.receipt(db,receiver,first,'received')
    assert service.detail(db,receiver,second)['recipients'][0]['received_at'] is None


def test_partial_sequences_are_per_project_preserve_prior_batches_and_project_title(environment, monkeypatch):
    from resource_request_models import ResourceRequest, ResourceRequestItem
    from annotation_models import AnnotationProject
    from resource_request_content import allocate_partial, annotation_context, prepare_data
    db,sender,receiver,outsider,request,project,service,notices=setup_data(environment,monkeypatch)
    child=AnnotationProject(id=uuid4(),order_no='AP-TEST.001',project_name='子订单',parent_project_id=project.id,child_sequence_no=1)
    db.add(child);db.commit()
    assert annotation_context(db,project.id)['collapse_languages']
    request.partial_requested=True
    request.items.append(ResourceRequestItem(id=uuid4(),sequence_no=1,requirement_detail='语言1'))
    db.commit();allocate_partial(db,request);db.commit()
    assert request.partial_sequence==1 and request.source_project_name_snapshot.startswith('部分语种（1）')
    second=ResourceRequest(id=uuid4(),request_no='RR-TEST2',source_type='annotation',request_category='annotation_trial',annotation_project_id=project.id,source_project_name_snapshot=project.project_name,request_detail='',partial_requested=True,items=[ResourceRequestItem(id=uuid4(),sequence_no=1)])
    db.add(second);db.commit();allocate_partial(db,second);db.commit()
    assert second.partial_sequence==2 and request.partial_sequence==1
    assert project.project_name=='隔离需求测试'
    allocate_partial(db,request);assert request.partial_sequence==1
    monkeypatch.setattr(AnnotationProject,'role_assignments',property(lambda self:[dict(role_code='project_manager',assignee_id=receiver.id,assignee_name=receiver.full_name)]))
    payload=SimpleNamespace(source_type='annotation',annotation_project_id=project.id,partial_requested=True)
    assert prepare_data(db,payload,{},request)['owner_id']==receiver.id


def test_notification_receiver_can_reply_without_project_write_permission(environment, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.resource_requests import dispatch_router
    db,sender,receiver,outsider,request,project,service,notices=setup_data(environment,monkeypatch)
    result=service.send(db,sender,request.id,service.DispatchWrite(kind='post',user_ids=[receiver.id],idempotency_key=str(uuid4())))
    app=FastAPI();app.include_router(dispatch_router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:receiver
    with TestClient(app) as client:
        assert client.get(f'/resource-request-dispatches/{result["id"]}').status_code==200
        assert client.put(f'/resource-request-dispatches/{result["id"]}/receipt',json={'status':'received'}).status_code==200
        app.dependency_overrides[get_current_user]=lambda:outsider
        assert client.get(f'/resource-request-dispatches/{result["id"]}').status_code==404


def test_business_notification_contains_project_name_and_request_number(environment, monkeypatch):
    db,users=environment
    import resource_request_dispatch as service
    captured=[]
    monkeypatch.setattr('crud.create_notifications_for_users',lambda *args,**kwargs:captured.append((args,kwargs)) or [])
    batch=SimpleNamespace(id=uuid4(),snapshot={'current_project_name':'部分语种（2）项目测试','request_no':'RR-TEST'})
    service.publish(db,[users[0].id],'已处理',batch)
    assert '部分语种（2）项目测试' in captured[0][0][2]
    assert 'RR-TEST' in captured[0][0][3]
    assert captured[0][1]['notification_type']=='resource_request_dispatch'


def test_chat_notification_list_and_count_filter_same_type_and_recipient(environment):
    from datetime import datetime
    from models import AppNotification
    from crud import get_notifications, count_unread_notifications
    from routers.notifications import router
    from routers.auth import get_current_user
    from database import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    db, (sender, receiver, outsider) = environment
    for user, kind, read in [(receiver, 'resource_request_dispatch', False), (receiver, 'resource_request_dispatch', True), (receiver, 'workflow', False), (outsider, 'resource_request_dispatch', False)]:
        db.add(AppNotification(id=uuid4(), recipient_user_id=user.id, title='项目名称需求通知', content='完整需求入口', notification_type=kind, is_read=read, created_at=datetime(2026, 10, 23, 12, 0)))
    db.commit()
    options = dict(channel='business', notification_type='resource_request_dispatch')
    rows = get_notifications(db, receiver.id, **options)
    assert len(rows) == 2 and all(row.recipient_user_id == receiver.id for row in rows)
    assert count_unread_notifications(db, receiver.id, **options) == 1
    assert count_unread_notifications(db, receiver.id, channel='business') == 2
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: receiver
    client = TestClient(app)
    assert len(client.get('/notifications/', params=options).json()) == 2
    assert client.get('/notifications/unread-count', params=options).json() == {'count': 1}
    unread = next(row for row in rows if not row.is_read)
    assert client.post(f'/notifications/{unread.id}/read').status_code == 200
    assert client.get('/notifications/unread-count', params=options).json() == {'count': 0}
    assert count_unread_notifications(db, receiver.id, channel='business') == 1


def test_notification_editor_entry_only_sender_and_opens_exact_request(environment, monkeypatch):
    db,sender,receiver,outsider,request,project,service,notices=setup_data(environment,monkeypatch)
    from models import AppNotification
    from crud import get_notifications
    from schemas import NotificationResponse
    from business_time import business_now
    from uuid import UUID
    batch=service.send(db,sender,request.id,service.DispatchWrite(kind='circle',user_ids=[receiver.id],idempotency_key=str(uuid4())))
    batch_id=UUID(batch['id'])
    for user in [sender,receiver]:
        db.add(AppNotification(id=uuid4(),recipient_user_id=user.id,title='项目需求通知',content='需求及回执',notification_type='resource_request_dispatch',related_entity_id=batch_id,is_read=False,created_at=business_now()))
    db.commit()
    sender_notice=get_notifications(db,sender.id,notification_type='resource_request_dispatch')[0]
    receiver_notice=get_notifications(db,receiver.id,notification_type='resource_request_dispatch')[0]
    assert NotificationResponse.model_validate(sender_notice).can_open_resource_request is True
    assert NotificationResponse.model_validate(receiver_notice).can_open_resource_request is False
    assert service.sender_request(db,sender,batch_id)['id']==request.id
    for user in [receiver,outsider]:
        with pytest.raises(HTTPException) as denied:service.sender_request(db,user,batch_id)
        assert denied.value.status_code==404


def test_each_dispatch_kind_allows_five_attempts_and_idempotent_retry(environment, monkeypatch):
    db,sender,receiver,outsider,request,project,service,notices=setup_data(environment,monkeypatch)
    from resource_request_send_history import history
    for kind in ['circle','post']:
        keys=[]
        for index in range(5):
            key=str(uuid4()); keys.append(key)
            payload=service.DispatchWrite(kind=kind,user_ids=[receiver.id],idempotency_key=key)
            service.send(db,sender,request.id,payload)
            service.send(db,sender,request.id,payload)
        assert len(history(db,request.id)['records'][kind])==5
        with pytest.raises(HTTPException) as full:
            service.send(db,sender,request.id,service.DispatchWrite(kind=kind,user_ids=[receiver.id],idempotency_key=str(uuid4())))
        assert full.value.status_code==409
    assert len(notices)==10
    request.request_detail='再次编辑不会重置发送次数';db.commit()
    assert [len(history(db,request.id)['records'][kind]) for kind in ['circle','post']]==[5,5]


def test_management_resends_keep_one_request_and_progress_and_count_old_audit(environment, monkeypatch):
    db,sender,receiver,outsider,request,project,service,notices=setup_data(environment,monkeypatch)
    from resource_request_service import send_resource_request
    from resource_request_send_history import history
    from resource_request_models import ResourceRequest, ResourceRequestProgressLog
    first_key=str(uuid4())
    send_resource_request(db,request.id,sender.id,first_key)
    request.progress_percent=40;request.request_status='in_progress';db.commit()
    send_resource_request(db,request.id,sender.id,first_key)
    assert len(history(db,request.id)['records']['development'])==1
    for index in range(4):send_resource_request(db,request.id,sender.id,str(uuid4()))
    assert len(history(db,request.id)['records']['development'])==5
    assert db.query(ResourceRequest).count()==1
    assert request.progress_percent==40 and request.request_status=='in_progress'
    assert db.query(ResourceRequestProgressLog).filter_by(progress_note='资源需求已发送').count()==5
    send_resource_request(db,request.id,sender.id,first_key)
    with pytest.raises(HTTPException) as full:send_resource_request(db,request.id,sender.id,str(uuid4()))
    assert full.value.status_code==409
    assert all(record['sent_at'].endswith('+08:00') for record in history(db,request.id)['records']['development'])


def test_management_targets_notifications_and_receipts_are_per_send(environment, monkeypatch):
    db,sender,receiver,outsider,request,project,service,notices=setup_data(environment,monkeypatch)
    from resource_request_service import send_resource_request
    from resource_request_send_history import history
    from resource_request_dispatch_models import ResourceRequestDispatch as Batch
    key=str(uuid4())
    send_resource_request(db,request.id,sender.id,key,[receiver.id])
    send_resource_request(db,request.id,sender.id,key,[receiver.id])
    assert len(notices)==1 and notices[0][0]==[receiver.id]
    with pytest.raises(HTTPException) as conflict:
        send_resource_request(db,request.id,sender.id,key,[outsider.id])
    assert conflict.value.status_code==409
    with pytest.raises(HTTPException) as invalid:
        send_resource_request(db,request.id,sender.id,str(uuid4()),[outsider.id])
    assert invalid.value.status_code==422
    send_resource_request(db,request.id,sender.id,str(uuid4()),[receiver.id])
    batches=db.query(Batch).filter_by(kind='development').order_by(Batch.created_at).all()
    service.receipt(db,receiver,batches[0].id,'received')
    service.receipt(db,receiver,batches[0].id,'processed')
    records=history(db,request.id)['records']['development']
    assert len(records)==2 and records[0]['recipients']==[receiver.full_name]
    assert [r['processed_count'] for r in records]==[1,0]
    assert service.detail(db,receiver,batches[1].id)['recipients'][0]['received_at'] is None
    assert len(notices)==4
