from datetime import datetime
from uuid import UUID,uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment,project


def setup_message(db,owner,member):
    from models import AnnotationChatMember,ChatProjectMessage,ChatProjectMessageFavorite
    parent=project(db,owner)
    db.add_all([AnnotationChatMember(project_id=parent.id,user_id=user.id) for user in (owner,member)])
    message=ChatProjectMessage(id=uuid4(),annotation_project_id=parent.id,sender_user_id=owner.id,sender_name='owner',content='标签检索消息',message_type='user',sequence_no=1,created_at=datetime(2026,11,27,12))
    db.add(message)
    db.add_all([ChatProjectMessageFavorite(id=uuid4(),message_id=message.id,user_id=user.id) for user in (owner,member)])
    db.commit()
    return parent,message


def test_shared_catalog_private_assignments_permissions_and_search(environment,monkeypatch):
    db,(owner,member,outsider)=environment
    import chat_favorite_tags as tags
    from chat_global_search import search_messages
    monkeypatch.setattr('chat_global_search.user_has_permission',lambda *args:True)
    parent,message=setup_message(db,owner,member)
    first=tags.create(db,owner,'  ＡＢＣ   需求 ')
    assert tags.create(db,member,'abc 需求')['id']==first['id']
    assert len(tags.catalog(db))==1 and first['color'].startswith('#')
    args=('annotation',parent.id,str(message.id))
    assert tags.message_tags(db,owner,*args,[UUID(first['id'])])['tags']==[first]
    assert tags.message_tags(db,member,*args)['tags']==[]
    with pytest.raises(HTTPException):tags.message_tags(db,outsider,*args,[UUID(first['id'])])
    found=search_messages(db,owner,'标签 消息',favorites_only=True,tag_id=UUID(first['id']),limit=1)
    assert found['total']==1 and found['items'][0]['tags']==[first]
    assert search_messages(db,member,'',favorites_only=True,tag_id=UUID(first['id']))['total']==0
    tags.message_tags(db,member,*args,[UUID(first['id'])])
    assert search_messages(db,member,'',favorites_only=True,tag_id=UUID(first['id']))['total']==1
    tags.message_tags(db,owner,*args,[])
    assert tags.message_tags(db,member,*args)['tags']==[first]
    from models import ChatProjectMessageFavorite
    db.query(ChatProjectMessageFavorite).filter_by(user_id=owner.id,message_id=message.id).delete();db.commit()
    with pytest.raises(HTTPException) as err:tags.message_tags(db,owner,*args,[UUID(first['id'])])
    assert err.value.status_code==409
    message.recalled_at=datetime(2026,11,27,13);db.commit()
    assert search_messages(db,member,'',favorites_only=True,tag_id=UUID(first['id']))['total']==0


def test_migration_creates_only_new_tables_and_can_repeat(environment):
    db,users=environment
    from sqlalchemy import inspect,text
    from tools.apply_chat_favorite_tags_migration import apply_migration
    connection=db.connection()
    connection.execute(text('DROP TABLE chat_favorite_message_tag'));connection.execute(text('DROP TABLE chat_favorite_tag'))
    apply_migration(connection);apply_migration(connection)
    assert inspect(connection).has_table('chat_favorite_tag')
    assert inspect(connection).has_table('chat_favorite_message_tag')
    assert connection.execute(text('SELECT count(*) FROM app_user')).scalar()==3


def test_discussion_tag_search_and_removed_membership(environment,monkeypatch):
    db,(owner,member,outsider)=environment
    from test_chat_mentions_all import setup_discussion
    from discussion_chat_models import DiscussionMessage,DiscussionMessageAction,DiscussionMember
    import chat_favorite_tags as tags
    from chat_global_search import search_messages
    monkeypatch.setattr('chat_global_search.user_has_permission',lambda *args:True)
    cid=setup_discussion(db,[owner,member,outsider]);tag=tags.create(db,member,'待跟进')
    for mid in [1,2]:
        db.add(DiscussionMessage(id=mid,room_id=cid,sender_id=owner.id,sender_name='owner',client_message_id=uuid4(),content='收藏内容',created_at=datetime(2026,11,27,12,mid)))
        db.add(DiscussionMessageAction(message_id=mid,user_id=member.id,user_name='member',favorited_at=datetime(2026,11,27,13)))
    db.commit()
    for mid in [1,2]:tags.message_tags(db,member,'discussion',cid,str(mid),[UUID(tag['id'])])
    first=search_messages(db,member,'',favorites_only=True,tag_id=UUID(tag['id']),limit=1)
    second=search_messages(db,member,'',favorites_only=True,tag_id=UUID(tag['id']),limit=1,offset=1)
    assert first['total']==second['total']==2 and first['has_more'] and not second['has_more']
    assert first['items'][0]['message_id']!=second['items'][0]['message_id']
    db.query(DiscussionMember).filter_by(room_id=cid,user_id=member.id).delete();db.commit()
    assert search_messages(db,member,'',favorites_only=True,tag_id=UUID(tag['id']))['total']==0
