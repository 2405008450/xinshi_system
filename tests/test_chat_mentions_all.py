"""@所有人、讨论提及和分页隔离回归；仅连接内存 SQLite。"""
from datetime import datetime,timedelta
from uuid import uuid4,UUID
import pytest
from sqlalchemy import event,func
from fastapi import HTTPException
from test_chat_participant_access import environment

@pytest.fixture
def chat_env(environment,monkeypatch):
    db,users=environment
    import project_chat_crud,annotation_chat_service,direct_chat_service
    from models import ChatProjectMessage,ChatProjectMention,AppNotification
    from discussion_chat_models import DiscussionMessage
    from chat_time import now
    callbacks=[]
    def defaults(mapper,connection,row):
        if hasattr(row,'id') and row.id is None:
            row.id=(connection.execute(__import__('sqlalchemy').select(func.max(DiscussionMessage.id))).scalar() or 0)+1 if isinstance(row,DiscussionMessage) else uuid4()
        if isinstance(row,ChatProjectMessage) and not row.sequence_no:row.sequence_no=(connection.execute(__import__('sqlalchemy').select(func.max(ChatProjectMessage.sequence_no))).scalar() or 0)+1
        if hasattr(row,'created_at') and row.created_at is None:row.created_at=now().replace(tzinfo=None)
    for model in [ChatProjectMessage,ChatProjectMention,AppNotification,DiscussionMessage]:
        event.listen(model,'before_insert',defaults);callbacks.append(model)
    monkeypatch.setattr(project_chat_crud,'_push_notifications',lambda *args:None)
    monkeypatch.setattr(direct_chat_service,'publish',lambda *args:None)
    import discussion_mentions
    monkeypatch.setattr(discussion_mentions,'eligible_users',lambda session,room,ids=None:session.query(type(users[0])).filter(type(users[0]).is_active.is_(True),type(users[0]).id.in_(ids) if ids is not None else True).all())
    try:yield db,users
    finally:
        for model in callbacks:event.remove(model,'before_insert',defaults)


def setup_discussion(db,users):
    from discussion_chat_models import DiscussionMember
    from discussion_chat_service import RESOURCE_ROOT
    from chat_session_category_models import ChatSessionCategory,ChatSessionCategoryFolder
    room=ChatSessionCategory(id=uuid4(),name='提及隔离测试',active=True,revision=1);db.add(room);db.flush()
    db.add(ChatSessionCategoryFolder(category_id=room.id,parent_key=RESOURCE_ROOT))
    db.add_all([DiscussionMember(room_id=room.id,user_id=user.id,last_read_id=0,pinned=False,starred=False) for user in users[:2]]);db.commit();return room.id


def test_discussion_mentions_all_and_explicit_invite_idempotency_read_recall(chat_env):
    db,(sender,receiver,outsider)=chat_env
    from models import AppNotification
    from discussion_chat_models import DiscussionMention,DiscussionMember
    from routers.discussion_chat import MessageCreate,PreferenceWrite,recall
    import discussion_chat_service as service
    from chat_mention_history import list_mentions
    room=setup_discussion(db,[sender,receiver,outsider])
    payload=MessageCreate(content='@所有人 请查看',mention_all=True,mentioned_user_ids=[receiver.id],client_message_id=uuid4())
    result=service.send(db,sender,room,payload)
    assert len(result['mentions'])==1 and result['metadata']['mention_all']
    assert db.query(DiscussionMention).count()==1 and db.query(AppNotification).count()==1
    assert not db.get(DiscussionMember,(room,outsider.id))
    assert service.send(db,sender,room,payload)['id']==result['id']
    assert db.query(AppNotification).count()==1
    catalog=service.catalog(db,receiver);row=next(row for row in catalog if row['project_id']==str(room))
    assert row['mention_unread']==1 and row['last_message']['mentions_me']
    inbox=list_mentions(db,receiver,project_type='discussion');assert inbox['total']==1
    assert inbox['items'][0]['message_id']==result['id']
    assert list_mentions(db,outsider,project_type='discussion')['total']==0
    service.preferences(db,receiver,room,PreferenceWrite(read_message_id=int(result['id'])))
    assert list_mentions(db,receiver,project_type='discussion')['items'][0]['unread'] is False
    assert next(row for row in service.catalog(db,receiver) if row['project_id']==str(room))['mention_unread']==0
    recall(room,int(result['id']),db,sender)
    assert list_mentions(db,receiver,project_type='discussion')['total']==0
    explicit=service.send(db,sender,room,MessageCreate(content='@outsider 请查看',mentioned_user_ids=[outsider.id],client_message_id=uuid4()))
    assert db.get(DiscussionMember,(room,outsider.id)) and len(explicit['mentions'])==1
    assert list_mentions(db,outsider,project_type='discussion')['total']==1
    with pytest.raises(HTTPException):service.send(db,sender,room,MessageCreate(content='非法目标',mentioned_user_ids=[uuid4()],client_message_id=uuid4()))


def test_project_all_exceeds_twenty_without_adding_nonmembers(chat_env):
    db,(sender,receiver,outsider)=chat_env
    from models import AppUser,AnnotationChatMember,ChatProjectMention
    from annotation_models import AnnotationProject
    from schemas import AnnotationProjectChatMessageCreate
    import annotation_chat_service as service
    project=AnnotationProject(id=uuid4(),order_no='AP-TEST',project_name='全体测试',created_by=sender.id);db.add(project)
    people=[receiver]+[AppUser(id=uuid4(),username=f'member-{index}',full_name=f'成员{index}',password_hash='disabled',is_active=True) for index in range(25)]
    db.add_all(people);db.flush()
    db.add_all([AnnotationChatMember(project_id=project.id,user_id=user.id,following=True,last_read_sequence=0) for user in [sender,*people]]);db.commit()
    message=service.send_message(db,project.id,sender,AnnotationProjectChatMessageCreate(content='@所有人 查看',mention_all=True,client_message_id=uuid4()))
    assert db.query(ChatProjectMention).filter_by(message_id=message.id).count()==26
    assert not db.get(AnnotationChatMember,(project.id,outsider.id))
    assert message.event_data['mention_all']
    assert service.send_message(db,project.id,sender,AnnotationProjectChatMessageCreate(content='重试',mention_all=True,client_message_id=message.client_message_id)).id==message.id


def test_direct_mentions_are_pair_only_and_global_inbox_cursor(chat_env):
    db,(sender,receiver,outsider)=chat_env
    from models import ChatDirectConversation,ChatDirectMember,ChatProjectMention
    from schemas import AnnotationProjectChatMessageCreate
    import direct_chat_service as service
    from chat_mention_history import list_mentions
    pair=ChatDirectConversation(id=uuid4(),user_low_id=min(sender.id,receiver.id),user_high_id=max(sender.id,receiver.id));db.add(pair)
    db.add_all([ChatDirectMember(conversation_id=pair.id,user_id=user.id,last_read_sequence=0) for user in [sender,receiver]]);db.commit()
    message=service.send_message(db,pair.id,sender,AnnotationProjectChatMessageCreate(content='@所有人',mention_all=True,client_message_id=uuid4()))
    assert db.query(ChatProjectMention).filter_by(message_id=message.id,mentioned_user_id=receiver.id).count()==1
    with pytest.raises(HTTPException):service.send_message(db,pair.id,sender,AnnotationProjectChatMessageCreate(content='不能拉入第三人',mentioned_user_ids=[outsider.id]))
    room=setup_discussion(db,[sender,receiver,outsider])
    from routers.discussion_chat import MessageCreate
    import discussion_chat_service as discussion
    discussion.send(db,sender,room,MessageCreate(content='@所有人 第二条',mention_all=True,client_message_id=uuid4()))
    first=list_mentions(db,receiver,limit=1)
    second=list_mentions(db,receiver,limit=1,before=first['next_before'])
    assert first['total']==2 and second['total']==2
    assert first['items'][0]['key']!=second['items'][0]['key']
    assert {first['items'][0]['project_type'],second['items'][0]['project_type']}=={'discussion','direct'}
    assert list_mentions(db,receiver,keyword='第二条')['total']==1
    assert list_mentions(db,outsider)['total']==0


def test_migration_is_create_only_repeatable(chat_env):
    db,_=chat_env
    from tools.apply_discussion_mentions_migration import apply_migration
    from discussion_chat_models import DiscussionMention
    DiscussionMention.__table__.drop(db.connection())
    apply_migration(db.connection());apply_migration(db.connection())
    assert db.query(DiscussionMention).count()==0


def test_translation_all_uses_existing_members_and_keeps_individual_limit(chat_env,monkeypatch):
    db,(sender,receiver,outsider)=chat_env
    from models import TranslationProject,ChatProjectEnabled,ChatProjectMemberPref,ChatProjectMention
    import project_chat_crud as service
    project=TranslationProject(id=uuid4(),order_no='TP-TEST-ALL',project_name='笔译群全体测试');db.add(project);db.flush()
    db.add(ChatProjectEnabled(id=uuid4(),project_id=project.id,enabled=True))
    db.add_all([ChatProjectMemberPref(project_id=project.id,user_id=user.id,last_read_sequence=0,pinned=False,starred=False) for user in [sender,receiver]]);db.commit()
    monkeypatch.setattr(service,'get_default_chat_recipient_ids',lambda *args:[])
    message=service.create_project_chat_message(db,project.id,sender,'@所有人 请查看',mention_all=True,client_message_id=uuid4())
    assert message.event_data['mention_all']
    assert db.query(ChatProjectMention).filter_by(message_id=message.id,mentioned_user_id=receiver.id).count()==1
    assert not db.get(ChatProjectMemberPref,(project.id,outsider.id))
    with pytest.raises(ValueError):service._normalize_mentioned_user_ids(sender.id,mentioned_user_ids=[uuid4() for _ in range(21)])
