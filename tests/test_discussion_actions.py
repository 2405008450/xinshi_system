from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_mentions_all import chat_env, setup_discussion
from test_chat_participant_access import environment


def test_recall_boundary_and_no_admin_bypass():
    from chat_time import now
    from chat_recall_policy import can_recall_own
    from annotation_chat_service import can_recall
    current=now();owner=uuid4();other=uuid4()
    assert can_recall_own(owner,owner,current-timedelta(hours=1),current=current)
    assert not can_recall_own(owner,owner,current-timedelta(hours=1,microseconds=1),current=current)
    assert not can_recall_own(owner,other,current,current=current)
    message=SimpleNamespace(message_type='user',sender_user_id=owner,created_at=current-timedelta(minutes=5),recalled_at=None)
    assert not can_recall(message,other,admin=True,now=current)


def test_discussion_actions_are_scoped_and_persisted(chat_env):
    db,(sender,reader,outsider)=chat_env
    from discussion_message_actions import set_action
    from discussion_chat_service import send,messages
    from routers.discussion_chat import MessageCreate,recall
    from chat_time import now
    from discussion_chat_models import DiscussionMessage
    room=setup_discussion(db,[sender,reader,outsider])
    row=send(db,sender,room,MessageCreate(content='收藏及收到',client_message_id=uuid4()))
    mid=int(row['id'])
    import discussion_chat_service
    set_action(db,reader,room,mid,'favorite',True)
    result=set_action(db,reader,room,mid,'acknowledgement',True)
    assert result['is_favorited'] and result['is_acknowledged']
    assert len(messages(db,reader,room,favorites_only=True)['items'])==1
    assert messages(db,sender,room,favorites_only=True)['items']==[]
    assert not messages(db,sender,room)['items'][0].get('is_favorited',False)
    assert messages(db,sender,room)['items'][0]['acknowledgements'][0]['user_id']==reader.id
    with pytest.raises(HTTPException): set_action(db,outsider,room,mid,'favorite',True)
    with pytest.raises(HTTPException): set_action(db,sender,room,mid,'acknowledgement',True)
    assert not set_action(db,reader,room,mid,'favorite',False)['is_favorited']
    with pytest.raises(HTTPException): recall(room,mid,db,reader)
    message=db.get(DiscussionMessage,mid);message.created_at=now()-timedelta(hours=2);db.commit()
    with pytest.raises(HTTPException): recall(room,mid,db,sender)


def test_discussion_summary_source_and_idempotency(chat_env,monkeypatch):
    db,(sender,reader,outsider)=chat_env
    import resource_issue_service as issues
    import resource_summary_service as summaries
    from resource_issue_schemas import IssueCreate
    from discussion_chat_service import send
    from routers.discussion_chat import MessageCreate
    from routers.resource_issues import locate_source
    room=setup_discussion(db,[sender,reader,outsider])
    message=send(db,sender,room,MessageCreate(content='讨论来源内容',client_message_id=uuid4()))
    monkeypatch.setattr(issues,'can_collect',lambda *args:True)
    monkeypatch.setattr(issues,'can_delegate',lambda *args:False)
    monkeypatch.setattr(issues,'is_admin',lambda *args:False)
    monkeypatch.setattr(issues,'audit',lambda *args:None)
    payload=IssueCreate(content='整理后的总结',category='problem',source_discussion_room_id=room,source_discussion_message_id=message['id'])
    row=issues.create_issue(db,reader,payload)
    assert row['source_type']=='discussion' and row['source_message_id']==message['id']
    assert row['source_content']=='讨论来源内容' and row['proposer_id']==str(sender.id)
    assert issues.create_issue(db,reader,payload)['already_collected']
    with pytest.raises(HTTPException): issues.create_issue(db,outsider,payload)
    source=locate_source(__import__('uuid').UUID(row['id']),db,reader)
    assert source['available'] and source['source_message_id']==message['id']


def test_actions_migration_is_create_only_and_repeatable(chat_env):
    db,_=chat_env
    from discussion_chat_models import DiscussionMessageAction,DiscussionIssueSource
    from tools.apply_discussion_actions_migration import apply_migration
    for model in (DiscussionIssueSource,DiscussionMessageAction): model.__table__.drop(db.connection())
    apply_migration(db.connection());apply_migration(db.connection())


def test_translation_recall_checks_ownership_and_one_hour(chat_env):
    db,(actor,reader,outsider)=chat_env
    from models import TranslationProject,ChatProjectMemberPref,ChatProjectMessage
    from chat_time import now
    from routers.project_chat import recall_translation_message
    project=TranslationProject(id=uuid4(),order_no='T-RECALL',project_name='撤回隔离测试')
    db.add(project);db.flush()
    db.add_all([ChatProjectMemberPref(project_id=project.id,user_id=user.id,last_read_sequence=0,pinned=False,starred=False) for user in (actor,reader)])
    message=ChatProjectMessage(id=uuid4(),project_id=project.id,sender_user_id=actor.id,sender_name=actor.full_name,content='待撤回',message_type='user',sequence_no=1,created_at=now().replace(tzinfo=None)-timedelta(minutes=59))
    db.add(message);db.commit()
    with pytest.raises(HTTPException):recall_translation_message(project.id,message.id,db,reader)
    with pytest.raises(HTTPException):recall_translation_message(project.id,message.id,db,outsider)
    message.created_at=now().replace(tzinfo=None)-timedelta(minutes=61);db.commit()
    with pytest.raises(HTTPException):recall_translation_message(project.id,message.id,db,actor)
    message.created_at=now().replace(tzinfo=None)-timedelta(minutes=59);db.commit()
    result=recall_translation_message(project.id,message.id,db,actor)
    assert result.recalled_at is not None and not result.can_recall
    assert message.content==''
