from uuid import uuid4,UUID
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from test_resource_request_dispatch import setup_data
from resource_request_dispatch_kinds import POSTING_KINDS

@pytest.mark.parametrize('kind',['wechat_public','xiaohongshu'])
@pytest.mark.parametrize('source',['annotation','interpretation'])
def test_new_posting_kinds_support_send_receipts_history_and_cancel(environment,monkeypatch,kind,source):
    db,sender,receiver,outsider,request,_project,service,notices=setup_data(environment,monkeypatch)
    if source=='interpretation':
        from interpretation_models import InterpretationProject
        project=InterpretationProject(id=uuid4(),order_no='IP-POSTING',project_name='口译项目')
        db.add(project);db.flush()
        request.source_type=source;request.request_category=source
        request.annotation_project_id=None;request.interpretation_project_id=project.id
    notes={'wechat_public':'公众号说明','xiaohongshu':'小红书说明'}
    request.request_content={'versions':[{'name':'发帖','content':'发布正文'}],'dispatch_notes':notes}
    db.commit()
    payload=service.DispatchWrite(kind=kind,user_ids=[receiver.id],idempotency_key=str(uuid4()))
    sent=service.send(db,sender,request.id,payload)
    assert service.send(db,sender,request.id,payload)['id']==sent['id']
    assert sent['kind']==kind
    assert sent['snapshot']['request_content']['dispatch_notes'][kind]==notes[kind]
    from resource_request_send_history import history
    records=history(db,request.id)['records']
    assert len(records[kind])==1
    assert len(records['post'])==0
    assert set(POSTING_KINDS)<=records.keys()
    batch_id=UUID(sent['id'])
    service.receipt(db,receiver,batch_id,'received')
    with pytest.raises(HTTPException) as error:
        service.receipt(db,receiver,batch_id,'processed')
    assert error.value.status_code==409
    from resource_request_execution import access
    assert access(db,receiver,batch_id)[0].kind==kind
    with pytest.raises(HTTPException):access(db,outsider,batch_id)
    from resource_request_cancellation import cancel_kind
    assert cancel_kind(db,sender,request.id,kind)['cancelled_count']==1
    assert cancel_kind(db,sender,request.id,kind)['cancelled_count']==0
    assert history(db,request.id)['records'][kind][0]['cancellation'] is not None


def test_new_kind_settings_and_note_schema_are_independent(environment):
    from resource_request_dispatch_defaults import catalog
    from resource_request_schemas import ResourceRequestDispatchNotes
    db,users=environment
    for kind in ['wechat_public','xiaohongshu']:
        result=catalog(db,users[0],kind)
        assert result['kind']==kind
        assert len(result['users'])==len(users)
    values=ResourceRequestDispatchNotes(wechat_public='公众号',xiaohongshu='小红书').model_dump()
    assert values['wechat_public']=='公众号' and values['xiaohongshu']=='小红书'
    assert values['post']==''
