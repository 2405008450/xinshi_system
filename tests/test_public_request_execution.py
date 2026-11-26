"""隔离验证公众号两阶段通知、权限、幂等与全体回执。"""
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_resource_request_dispatch import setup_data


@pytest.mark.parametrize('source_type', ['annotation', 'interpretation'])
def test_defaults_for_both_modules_and_saved_override(environment, monkeypatch, source_type):
    db, (sender, receiver, other) = environment
    import resource_request_dispatch_defaults as service
    from resource_request_dispatch_models import ResourceRequestDispatchDefault as Config
    receiver.full_name='王露';other.full_name='彭舒婷';other.username='shuting'
    db.add(Config(kind='circle',user_ids=[str(receiver.id)],revision=1))
    db.commit()
    monkeypatch.setattr(service,'can_manage',lambda *_:True)
    all_ids={str(p.id) for p in [sender,receiver,other]}
    assert set(service.catalog(db,sender,'circle',source_type)['user_ids'])==all_ids
    assert service.catalog(db,sender,'wechat_public',source_type)['user_ids']==[str(receiver.id)]
    assert service.catalog(db,sender,'xiaohongshu',source_type)['user_ids']==[str(other.id)]
    saved=service.save(db,sender,'wechat_public',service.DefaultWrite(user_ids=[other.id],revision=0))
    assert service.catalog(db,sender,'wechat_public',source_type)['user_ids']==[str(other.id)]
    service.save(db,sender,'wechat_public',service.DefaultWrite(user_ids=None,revision=saved['revision']))
    assert service.catalog(db,sender,'wechat_public',source_type)['user_ids']==[str(receiver.id)]
    other.is_active=False;db.commit()
    assert str(other.id) not in service.catalog(db,sender,'circle',source_type)['user_ids']


def test_execute_then_broadcast_once_and_collect_everyones_receipts(environment,monkeypatch):
    db,sender,receiver,outsider,request,project,dispatch,notices=setup_data(environment,monkeypatch)
    import resource_request_public_execution as service
    from resource_request_dispatch_models import ResourceRequestDispatch as Batch
    from resource_request_send_history import history
    from resource_request_cancellation import cancel_kind
    sent=dispatch.send(db,sender,request.id,dispatch.DispatchWrite(kind='wechat_public',user_ids=[receiver.id],idempotency_key=str(uuid4())))
    batch_id=UUID(sent['id'])
    assert sent['public_execution'] and sent['broadcast'] is None and len(notices)==1
    payload=service.PublicExecutionWrite(content='已发布公众号，链接 example.test',idempotency_key=str(uuid4()))
    for actor in [sender,outsider]:
        with pytest.raises(HTTPException) as denied:service.execute(db,actor,batch_id,payload)
        assert denied.value.status_code==404
    with pytest.raises(HTTPException) as pending:service.execute(db,receiver,batch_id,payload)
    assert pending.value.status_code==409
    dispatch.receipt(db,receiver,batch_id,'received')
    with pytest.raises(HTTPException):
        service.execute(db,receiver,batch_id,service.PublicExecutionWrite(content=' ',idempotency_key=str(uuid4())))
    result=service.execute(db,receiver,batch_id,payload)
    broadcast_id=UUID(result['broadcast']['id'])
    assert {p['user_id'] for p in result['broadcast']['recipients']}=={str(p.id) for p in [sender,receiver,outsider]}
    assert result['execution_replies'][0]['content']==payload.content
    assert result['recipients'][0]['processed_at'].endswith('+08:00')
    count=len(notices)
    service.execute(db,receiver,batch_id,payload)
    assert len(notices)==count
    assert db.query(Batch).filter_by(kind='wechat_broadcast').count()==1
    received=dispatch.detail(db,outsider,broadcast_id)
    assert received['snapshot']['public_execution_content']==payload.content
    with pytest.raises(HTTPException):dispatch.receipt(db,outsider,broadcast_id,'processed')
    dispatch.receipt(db,outsider,broadcast_id,'received')
    dispatch.receipt(db,outsider,broadcast_id,'processed')
    item=history(db,request.id)['records']['wechat_public'][0]
    assert next(p for p in item['broadcast']['recipients'] if p['user_id']==str(outsider.id))['processed_at']
    assert len(history(db,request.id)['records']['circle'])==0
    assert cancel_kind(db,sender,request.id,'wechat_public')['cancelled_count']==2
    with pytest.raises(HTTPException):dispatch.receipt(db,outsider,broadcast_id,'processed')
    with pytest.raises(HTTPException):service.execute(db,receiver,batch_id,payload)


def test_both_executors_and_retry_dont_duplicate_all_notification(environment,monkeypatch):
    db,sender,receiver,other,request,project,dispatch,notices=setup_data(environment,monkeypatch)
    from resource_request_public_execution import PublicExecutionWrite,execute
    from resource_request_dispatch_models import ResourceRequestDispatch as Batch
    sent=dispatch.send(db,sender,request.id,dispatch.DispatchWrite(kind='wechat_public',user_ids=[receiver.id,other.id],idempotency_key=str(uuid4())))
    batch_id=UUID(sent['id'])
    for person in [receiver,other]:
        dispatch.receipt(db,person,batch_id,'received')
        execute(db,person,batch_id,PublicExecutionWrite(content=f'{person.username}已发布',idempotency_key=str(uuid4())))
    assert db.query(Batch).filter_by(kind='wechat_broadcast').count()==1
    assert len(dispatch.detail(db,sender,batch_id)['execution_replies'])==2
