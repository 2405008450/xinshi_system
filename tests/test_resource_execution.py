"""仅使用隔离 SQLite 验证执行平台授权、快照、幂等及渠道操作记录。"""
from uuid import uuid4,UUID
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_resource_request_dispatch import setup_data


def setup_execution(environment,monkeypatch):
    db,sender,receiver,outsider,request,project,dispatch,notices=setup_data(environment,monkeypatch)
    from resource_channel_service import save_channel
    from resource_channel_schemas import ChannelWrite
    channel=save_channel(db,sender,ChannelWrite(name='虚拟平台',category='national',user_ids=[receiver.id]))
    alien=save_channel(db,sender,ChannelWrite(name='他人的平台',category='national',user_ids=[outsider.id]));db.commit()
    post=dispatch.send(db,sender,request.id,dispatch.DispatchWrite(kind='post',user_ids=[receiver.id],idempotency_key=str(uuid4())))
    return db,sender,receiver,outsider,request,dispatch,notices,UUID(post['id']),channel,alien


def test_execution_only_own_platforms_and_post_recipient(environment,monkeypatch):
    db,sender,receiver,outsider,request,dispatch,notices,batch_id,channel,alien=setup_execution(environment,monkeypatch)
    import resource_request_execution as service
    assert [p['name'] for p in service.channels(db,receiver,batch_id)['items']]==['虚拟平台']
    for person in [sender,outsider]:
        with pytest.raises(HTTPException):service.channels(db,person,batch_id)
    payload=service.ExecutionWrite(platform_ids=[UUID(channel['id'])],content='已发帖',idempotency_key=str(uuid4()))
    with pytest.raises(HTTPException) as pending:service.send(db,receiver,batch_id,payload)
    assert pending.value.status_code==409
    dispatch.receipt(db,receiver,batch_id,'received')
    with pytest.raises(HTTPException) as forbidden:
        service.send(db,receiver,batch_id,service.ExecutionWrite(platform_ids=[UUID(alien['id'])],idempotency_key=str(uuid4())))
    assert forbidden.value.status_code==422
    result=service.send(db,receiver,batch_id,payload)
    assert result['execution_replies'][0]['platforms'][0]['name']=='虚拟平台'
    assert result['recipients'][0]['processed_at']
    assert result['execution_replies'][0]['created_at'].endswith('+08:00')
    service.send(db,receiver,batch_id,payload)
    assert len(service.replies(db,[batch_id]))==1 and len(notices)==3
    with pytest.raises(HTTPException):
        service.send(db,receiver,batch_id,service.ExecutionWrite(platform_ids=[UUID(channel['id'])],content='不同内容',idempotency_key=payload.idempotency_key))


def test_channel_edit_delete_preserves_execution_and_audits(environment,monkeypatch):
    db,sender,receiver,outsider,request,dispatch,notices,batch_id,channel,alien=setup_execution(environment,monkeypatch)
    import resource_request_execution as service
    from resource_channel_service import save_channel,delete_channel,channel_history
    from resource_channel_schemas import ChannelWrite
    from resource_request_send_history import history
    dispatch.receipt(db,receiver,batch_id,'received')
    service.send(db,receiver,batch_id,service.ExecutionWrite(platform_ids=[UUID(channel['id'])],content='已发布',idempotency_key=str(uuid4())))
    saved=save_channel(db,receiver,ChannelWrite(name='平台已改名',category='national',user_ids=[receiver.id],revision=channel['revision']),UUID(channel['id']));db.commit()
    delete_channel(db,receiver,UUID(channel['id']),saved['revision']);db.commit()
    assert service.channels(db,receiver,batch_id)['items']==[]
    record=history(db,request.id)['records']['post'][0]
    assert record['execution_replies'][0]['platforms'][0]['name']=='虚拟平台'
    changes=channel_history(db,UUID(channel['id']))
    assert {row['action'] for row in changes}=={'create','update','delete'}
    assert changes[0]['before']['name']=='平台已改名'
    assert all(row['created_at'].endswith('+08:00') for row in changes)


def test_execution_rejects_non_post_notifications(environment,monkeypatch):
    db,sender,receiver,outsider,request,project,dispatch,notices=setup_data(environment,monkeypatch)
    import resource_request_execution as service
    circle=dispatch.send(db,sender,request.id,dispatch.DispatchWrite(kind='circle',user_ids=[receiver.id],idempotency_key=str(uuid4())))
    with pytest.raises(HTTPException):service.channels(db,receiver,UUID(circle['id']))


def test_processed_requires_platform_reply_and_nonempty_description(environment,monkeypatch):
    db,sender,receiver,outsider,request,dispatch,notices,batch_id,channel,alien=setup_execution(environment,monkeypatch)
    import resource_request_execution as service
    dispatch.receipt(db,receiver,batch_id,'received')
    with pytest.raises(HTTPException) as missing:
        dispatch.receipt(db,receiver,batch_id,'processed')
    assert missing.value.status_code==409
    assert dispatch.detail(db,sender,batch_id)['recipients'][0]['processed_at'] is None
    with pytest.raises(HTTPException) as blank:
        service.send(db,receiver,batch_id,service.ExecutionWrite(platform_ids=[UUID(channel['id'])],content='   ',idempotency_key=str(uuid4())))
    assert blank.value.status_code==422
    assert service.replies(db,[batch_id])==[]
    reply=service.send(db,receiver,batch_id,service.ExecutionWrite(platform_ids=[UUID(channel['id'])],content='已发布招募帖，链接：https://example.test/post/1',idempotency_key=str(uuid4())))
    assert reply['recipients'][0]['processed_at']
    assert reply['execution_replies'][0]['user_id']==str(receiver.id)
    assert reply['execution_replies'][0]['platforms'][0]['name']=='虚拟平台'
    assert 'post/1' in reply['execution_replies'][0]['content']
    assert dispatch.receipt(db,receiver,batch_id,'processed')['recipients'][0]['processed_at']
