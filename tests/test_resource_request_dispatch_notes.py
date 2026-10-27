"""三类需求说明复用 JSON 内容，隔离验证保存、兼容和发送快照。"""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_chat_participant_access import environment
from test_resource_request_dispatch import setup_data
from resource_request_schemas import ResourceRequestContent, ResourceRequestWrite
from resource_request_content import prepare_data


def test_notes_optional_independent_and_legacy_updates_preserve_values():
    assert ResourceRequestContent().dispatch_notes.model_dump() == {'circle':'','post':'','development':''}
    previous=SimpleNamespace(request_content={'dispatch_notes':{'circle':'仅晚间联系','post':'请发指定平台','development':'先找熟手'}})
    payload=ResourceRequestWrite(source_type='other',request_category='other',other_source_name='测试',request_content={'versions':[]})
    data=prepare_data(None,payload,payload.model_dump(),previous)
    assert data['request_content']['dispatch_notes'] == previous.request_content['dispatch_notes']
    payload=payload.model_copy(update={'request_content':ResourceRequestContent(dispatch_notes={'circle':''})})
    data=prepare_data(None,payload,payload.model_dump(),previous)
    assert data['request_content']['dispatch_notes'] == {'circle':'','post':'请发指定平台','development':'先找熟手'}
    with pytest.raises(ValueError):
        ResourceRequestContent(dispatch_notes={'post':'x'*10001})


def test_saved_notes_are_in_send_snapshot_and_later_changes_do_not_rewrite_history(environment,monkeypatch):
    db,sender,receiver,_outsider,request,_project,service,_notices=setup_data(environment,monkeypatch)
    from resource_request_models import ResourceRequest
    notes={'circle':'晚上发圈\n保留换行','post':'发布到招聘平台','development':'先找熟悉项目的资源'}
    request.request_content={'versions':[],'dispatch_notes':notes}
    db.commit();db.expire(request,['request_content'])
    assert db.get(ResourceRequest,request.id).request_content['dispatch_notes'] == notes
    result=service.send(db,sender,request.id,service.DispatchWrite(kind='circle',user_ids=[receiver.id],idempotency_key=str(uuid4())))
    assert result['snapshot']['request_content']['dispatch_notes'] == notes
    request.request_content={'versions':[],'dispatch_notes':{'circle':'下一批的新说明'}}
    db.commit()
    from uuid import UUID
    assert service.detail(db,receiver,UUID(result['id']))['snapshot']['request_content']['dispatch_notes'] == notes
