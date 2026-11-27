from uuid import uuid4
from types import SimpleNamespace
import pytest
from test_chat_participant_access import environment
from test_discussion_search import history

def roles(db,people):
 from models import Role,UserRole
 for role_name,users in people:
  role=Role(id=uuid4(),role_name=role_name);db.add(role);db.flush()
  for person in users:db.add(UserRole(id=uuid4(),user_id=person.id,role_id=role.id))
 db.commit()

def test_role_group_is_current_members_active_unique_and_not_all(history):
 from models import AppUser
 from discussion_mentions import recipients
 from chat_mention_recipients import resolve_mentions,manager_role_user_ids
 db,actor,member,outsider,room,_=history
 roles(db,[('项目经理',[member,outsider]),('客户专员',[member])])
 inactive=AppUser(id=uuid4(),username='disabled-manager',password_hash='disabled',is_active=False)
 deleted=AppUser(id=uuid4(),username='deleted-manager',password_hash='disabled',is_active=True,is_deleted=True)
 db.add_all([inactive,deleted]);db.commit()
 roles(db,[('客户经理',[inactive,deleted])])
 payload=SimpleNamespace(mentioned_user_ids=[],mention_all=False,mention_managers=True)
 people,_=recipients(db,actor,room,payload)
 assert [person.id for person in people]==[member.id]
 assert resolve_mentions(db,'discussion',room,actor,mention_managers=True)==[member.id]
 assert manager_role_user_ids(db)=={member.id,outsider.id}
 assert resolve_mentions(db,'discussion',room,member,mention_managers=True)==[]
 member.is_active=False;db.commit()
 assert recipients(db,actor,room,payload)[0]==[]


def test_role_group_send_creates_real_at_relation_without_invitations(history,monkeypatch):
 import discussion_chat_service as service
 from routers.discussion_chat import MessageCreate
 from discussion_chat_models import DiscussionMember
 db,actor,member,outsider,room,_=history
 roles(db,[('项目经理',[member,outsider])])
 # 隔离通知保存，检验角色展开、持久提及及成员范围，不发送外部事件。
 import crud
 monkeypatch.setattr(crud,'create_notifications_for_users',lambda *a,**kw:[])
 result=service.send(db,actor,room,MessageCreate(content='@所有项目经理+客户经理 查看',mention_managers=True,client_message_id=uuid4()))
 assert {row['mentioned_user_id'] for row in result['mentions']}=={str(member.id)}
 assert not any(row['is_all'] for row in result['mentions'])
 assert not db.query(DiscussionMember).filter_by(room_id=room,user_id=outsider.id).first()
