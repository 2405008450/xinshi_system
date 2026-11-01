from uuid import uuid4,UUID
import pytest
from fastapi import HTTPException
from test_technical_development import environment,setup,payload
import technical_development as tasks
import technical_task_conversations as service
import discussion_chat_service as discussion
import chat_session_category_service as categories
from chat_session_category_models import ChatSessionCategory as Category,ChatSessionCategoryFolder as Folder
from discussion_chat_models import DiscussionMember,DiscussionMessage
from chat_access_service import is_member,visible_ids


def test_create_reopen_department_members_and_dynamic_title(setup,monkeypatch):
    db,(owner,executor,outsider)=setup
    monkeypatch.setattr(discussion,'publish',lambda *_:None)
    task=tasks.create_task(db,owner,payload(owner,executor,'接口开发'))
    first=service.open_conversation(db,owner,task['id'])
    assert service.open_conversation(db,executor,task['id'])['room_id']==first['room_id']
    assert db.query(service.TaskConversation).count()==1
    assert is_member(db,'discussion',first['room_id'],owner)
    assert is_member(db,'discussion',first['room_id'],executor)
    assert not is_member(db,'discussion',first['room_id'],outsider)
    assert db.get(Folder,first['room_id']).parent_key==service.ROOT_ID
    assert tasks.list_tasks(db,owner)['items'][0]['conversation']['room_id']==first['room_id']
    task_row=tasks.get_task(db,task['id']);task_row.name='调整后的接口开发';db.commit()
    assert '调整后的接口开发' in discussion.catalog(db,owner)[0]['title']
    assert categories.catalog(db,owner)['technical_access'] is True


def test_outsider_member_cannot_read_search_or_see_categories(setup,monkeypatch):
    db,(owner,executor,outsider)=setup
    monkeypatch.setattr(discussion,'publish',lambda *_:None)
    task=tasks.create_task(db,owner,payload(owner,executor))
    room=service.open_conversation(db,owner,task['id'])['room_id']
    db.add(DiscussionMember(room_id=room,user_id=outsider.id));db.commit()
    assert not is_member(db,'discussion',room,outsider)
    assert room not in {uid for uid, in visible_ids(db,'discussion',outsider)}
    assert not discussion.catalog(db,outsider)
    assert room not in {UUID(row['id']) for row in categories.catalog(db,outsider)['items']}
    assert categories.catalog(db,outsider)['technical_access'] is False
    with pytest.raises(HTTPException): discussion.require_room(db,outsider,room)
    with pytest.raises(HTTPException): service.open_conversation(db,outsider,task['id'])
    owner.department='销售';db.commit()
    assert not is_member(db,'discussion',room,owner)


def test_existing_general_moves_pins_and_keeps_messages(setup):
    db,(owner,executor,outsider)=setup
    room=Category(id=uuid4(),name=service.GENERAL_NAME,updated_by=owner.id)
    db.add(room);db.flush()
    db.add(DiscussionMember(room_id=room.id,user_id=outsider.id))
    message=DiscussionMessage(room_id=room.id,sender_id=outsider.id,sender_name='原成员',client_message_id=uuid4(),content='原来的聊天记录')
    db.add(message);db.commit()
    result=service.configure_general(db,actor=owner,expected_revision=1);db.commit()
    assert result['moved'] and result['pinned']
    assert db.get(Folder,room.id).parent_key==service.ROOT_ID
    assert db.get(DiscussionMessage,message.id).content=='原来的聊天记录'
    assert db.get(DiscussionMember,(room.id,outsider.id)) is not None
    assert not is_member(db,'discussion',room.id,outsider)
    assert db.get(DiscussionMember,(room.id,owner.id)).pinned
    assert db.get(DiscussionMember,(room.id,executor.id)).pinned
    assert next(row for row in categories.catalog(db,owner)['items'] if row['id']==str(room.id))['fixed_top'] is True


def test_category_admin_cannot_bypass_department_and_migration_idempotent(setup,monkeypatch):
    from routers.chat_session_categories import create,CategoryCreate
    from tools.apply_technical_task_conversation_migration import apply_migration
    db,(owner,executor,outsider)=setup
    monkeypatch.setattr(categories,'can_manage_folders',lambda *_:True)
    with pytest.raises(HTTPException) as error: create(CategoryCreate(name='越权会话',parent_key=UUID(service.ROOT_ID),conversation=True),db,outsider)
    assert error.value.status_code==403
    service.TaskConversation.__table__.drop(db.connection());db.commit()
    with db.bind.begin() as connection: apply_migration(connection)
    with db.bind.begin() as connection: apply_migration(connection)
    assert service.ready(db)
