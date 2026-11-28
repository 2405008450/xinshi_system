from uuid import uuid4
from types import SimpleNamespace
import pytest
from test_chat_participant_access import environment
from routers.chat_project_entry import status,create,CreateRequest

@pytest.mark.parametrize('module',['translation','interpretation','recruitment'])
def test_existing_project_room_enters_without_resend(environment,monkeypatch,module):
    db,(owner,member,outsider)=environment
    import routers.chat_project_entry as service
    from chat_session_category_models import ChatSessionCategory as Category
    from discussion_chat_models import DiscussionMember
    project=SimpleNamespace(order_no='TEST-001')
    room=Category(id=uuid4(),name='隔离项目会话',active=True,revision=1,updated_by=owner.id)
    db.add_all([room,DiscussionMember(room_id=room.id,user_id=member.id,last_read_id=0,pinned=False,starred=False)]);db.commit()
    monkeypatch.setattr(service,'project_and_room',lambda *args:(project,room))
    monkeypatch.setattr(service,'user_has_permission',lambda *args:True)
    def forbidden(*args,**kw):raise AssertionError('进入已有会话不得发送概览')
    monkeypatch.setattr('project_delivery.send',forbidden);monkeypatch.setattr('translation_chat_delivery.send',forbidden)
    result=status(module,uuid4(),db,member)
    assert result['joined'] and result['target']['projectId']==str(room.id)
    entered=create(module,uuid4(),CreateRequest(request_key=uuid4()),db,member)
    assert entered['joined'] and db.query(DiscussionMember).count()==1
    joined=create(module,uuid4(),CreateRequest(request_key=uuid4()),db,owner)
    assert joined['joined'] and db.query(DiscussionMember).count()==2


def test_native_translation_is_reused(environment,monkeypatch):
    db,(owner,member,outsider)=environment
    import routers.chat_project_entry as service
    from models import ChatProjectEnabled
    project=SimpleNamespace(id=uuid4(),order_no='TP-TEST',project_name='既有笔译会话')
    db.add(ChatProjectEnabled(id=uuid4(),project_id=project.id,enabled=True,enabled_by=owner.id));db.commit()
    monkeypatch.setattr(service,'project_and_room',lambda *args:(project,None))
    monkeypatch.setattr(service,'user_has_permission',lambda *args:True)
    def forbidden(*args,**kw):raise AssertionError('已有原生笔译会话不得新建群')
    monkeypatch.setattr('translation_chat_delivery.send',forbidden)
    assert service.status('translation',project.id,db,member)['created']
    result=service.create('translation',project.id,CreateRequest(request_key=uuid4()),db,member)
    assert result['joined'] and result['target']['projectType']=='translation'
