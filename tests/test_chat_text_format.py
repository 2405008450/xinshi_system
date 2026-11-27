from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_discussion_search import history
from chat_text_format import validate_format

def document(text,kind='underline',color='#dc2626'):
 return {'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':text,'marks':[{'type':kind,'attrs':{'color':color}}]}]}]}


def test_format_allowlist_and_plain_text_consistency():
 assert validate_format('文字',document(' 文字 '))['content'][0]['content'][0]['text']=='文字'
 for kind,color in [('underline','#111827'),('underline','#2563eb'),('textColor','#dc2626'),('highlight','#dbeafe'),('highlight','#fef08a')]:
  assert validate_format('文字',document('文字',kind,color))
 for invalid in [document('不同正文'),document('文字','link','javascript:alert(1)'),document('文字','underline','url(https://bad)'),{'type':'doc','content':[None]},{'type':'doc','content':[{'type':'paragraph','content':[{'type':'image','attrs':{'src':'bad'}}]}]}]:
  with pytest.raises(HTTPException) as error:validate_format('文字',invalid)
  assert error.value.status_code==422


def test_discussion_format_roundtrip_idempotency_access_and_recall(history):
 import discussion_chat_service as service
 from routers.discussion_chat import MessageCreate
 from discussion_chat_models import DiscussionMessage,DiscussionMessageFormat
 db,actor,_,outsider,room,_=history
 payload=MessageCreate(content='格式消息',content_json=document('格式消息'),client_message_id=uuid4())
 sent=service.send(db,actor,room,payload)
 assert sent['content']=='格式消息' and sent['content_json']==validate_format('格式消息',document('格式消息'))
 assert service.send(db,actor,room,payload)['id']==sent['id']
 assert db.query(DiscussionMessageFormat).count()==1
 assert service.messages(db,actor,room)['items'][-1]['content_json']==sent['content_json']
 with pytest.raises(HTTPException):service.messages(db,outsider,room)
 row=db.get(DiscussionMessage,int(sent['id']));row.recalled_at=row.created_at;db.flush()
 assert service.serialize(db,row,actor)['content_json'] is None


def test_new_format_table_migration_is_repeatable(environment):
 from discussion_chat_models import DiscussionMessageFormat
 from tools.apply_chat_message_format_migration import apply_migration
 from sqlalchemy import inspect
 db,_=environment
 DiscussionMessageFormat.__table__.drop(db.connection())
 apply_migration(db.connection());apply_migration(db.connection())
 assert inspect(db.connection()).has_table('chat_discussion_message_format')


def test_native_and_discussion_format_search_combines_filters(history,monkeypatch):
 import discussion_chat_service as service
 from discussion_chat_models import DiscussionMessageFormat
 from chat_history_search import search_chat_history
 import chat_history_search
 from sqlalchemy import false
 # PostgreSQL 链接正则不属于本例，SQLite 中排除无链接的独立分支。
 monkeypatch.setattr(chat_history_search,'_link_query',lambda query,keyword:query.filter(false()))
 from models import ChatProjectMessage
 from test_chat_participant_access import project
 from chat_time import now
 db,actor,colleague,_,room,_=history
 doc=document('正文','underline','#dc2626')
 doc['content'][0]['content'][0]['marks'].append({'type':'bold'})
 db.add(DiscussionMessageFormat(message_id=8,content_json=document('普通文字，不是文件或小程序')))
 native=project(db,actor)
 db.add_all([ChatProjectMessage(id=uuid4(),annotation_project_id=native.id,sender_user_id=actor.id,sender_name='发送人',content='正文',content_json=doc,created_at=now(),updated_at=now()),ChatProjectMessage(id=uuid4(),annotation_project_id=native.id,sender_user_id=colleague.id,sender_name='其他人',content='普通',created_at=now(),updated_at=now())]);db.commit()
 assert [r['id'] for r in service.messages(db,actor,room,format_filters='underline_red')['items']]==['8']
 assert service.messages(db,actor,room,format_filters='bold')['items']==[]
 query=dict(project_type='annotation',project_id=native.id,user_id=actor.id)
 assert search_chat_history(db,**query,format_filters='underline_red,bold',keyword='正文',sender_user_id=actor.id)['total']==1
 assert search_chat_history(db,**query,format_filters='underline_blue')['total']==0
 assert search_chat_history(db,**query,format_filters='bold',sender_user_id=colleague.id)['total']==0
 with pytest.raises(HTTPException):search_chat_history(db,**query,format_filters='unknown')


def test_annotation_send_preserves_format(environment):
 from routers.annotation_chat import start
 import annotation_chat_service as service
 from schemas import AnnotationProjectChatMessageCreate
 from test_chat_participant_access import project
 db,(actor,_,_)=environment
 from sqlalchemy import event
 from models import ChatProjectMessage
 def defaults(session,*args):
  for message in session.new:
   if isinstance(message,ChatProjectMessage):
    if message.id is None:message.id=uuid4()
    if message.sequence_no is None:message.sequence_no=1
 event.listen(db,'before_flush',defaults)
 row=project(db,actor);start(row.id,db,actor)
 payload=AnnotationProjectChatMessageCreate(content='新格式',content_json=document('新格式'),client_message_id=uuid4())
 sent=service.send_message(db,row.id,actor,payload)
 assert sent.content=='新格式' and sent.content_json==validate_format('新格式',document('新格式'))
