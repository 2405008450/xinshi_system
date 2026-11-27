"""图片搜索使用隔离 SQLite；覆盖正文截图、富文本、附件去重及跨来源游标。"""
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import false
from test_chat_participant_access import environment,project
from chat_time import now

@pytest.fixture
def images(environment,monkeypatch):
 import chat_history_search as history
 from models import ChatProjectMessage,ChatProjectAttachment,ChatProjectMessageAttachment
 from editor_screenshot_models import EditorScreenshot,EditorScreenshotBlob
 from editor_screenshot_service import signed_reference
 db,(actor,colleague,outsider)=environment
 # 链接正则由 PostgreSQL 执行，本例 SQLite 中不启用无链接的分支。
 monkeypatch.setattr(history,'_link_query',lambda query,keyword:query.filter(false()))
 root=project(db,actor);foreign=project(db,actor,'AP-TEST-OTHER');shots=[];clock=now()
 for i in range(7):
  digest=f'{i+1:064x}'
  if i!=5:db.add(EditorScreenshotBlob(sha256=digest,content=b'png',content_type='image/png',byte_size=3))
  shot=EditorScreenshot(id=uuid4(),blob_sha256=digest if i!=5 else None,uploaded_by=actor.id,retention_kind='chat',expires_at=clock+timedelta(days=30))
  db.add(shot);shots.append(shot)
 def token(index):return f'![截图]({signed_reference(shots[index].id)})'
 def message(seq,content,doc=None,foreign_room=False,recalled=False):
  row=ChatProjectMessage(id=uuid4(),annotation_project_id=foreign.id if foreign_room else root.id,sender_user_id=actor.id if seq%2 else colleague.id,sender_name='人员',content=content,content_json=doc,created_at=clock+timedelta(minutes=seq),updated_at=clock,sequence_no=seq,recalled_at=clock if recalled else None)
  db.add(row);db.flush();return row
 def attachment(message,storage):
  row=ChatProjectAttachment(id=uuid4(),uploaded_by=actor.id,original_name='附件图片.png',storage_name=storage,content_type='image/png',file_size=3)
  db.add(row);db.flush();db.add(ChatProjectMessageAttachment(id=uuid4(),message_id=message.id,attachment_id=row.id))
 m1=message(1,'旧图');attachment(m1,'ordinary.png')
 m2=message(2,'现有截图 '+token(0)+' '+token(1),{'type':'doc','content':[{'type':'image','attrs':{'src':signed_reference(shots[0].id)}}]})
 m3=message(3,'富文本截图',{'type':'doc','content':[{'type':'image','attrs':{'src':signed_reference(shots[2].id)}}]})
 message(4,'已撤回 '+token(3),recalled=True)
 m5=message(5,'重复存储 '+token(4));attachment(m5,'screenshot:'+str(shots[4].id))
 message(6,'过期截图 '+token(5));message(7,'其他会话 '+token(6),foreign_room=True)
 db.commit()
 return db,actor,colleague,root,shots,history


def search(images,**kwargs):
 db,actor,_,root,_,history=images
 return history.search_chat_history(db,project_type='annotation',project_id=root.id,user_id=actor.id,kind='image',**kwargs)


def test_images_count_all_sources_once_and_cursor_is_complete(images):
 result=search(images,limit=2);assert result['total']==6 and result['totals']['image']==6
 found=[];cursor=None
 for i in range(5):
  page=search(images,limit=2,cursor=cursor)
  found.extend((str(row['message_id']),row['attachment']['id'],row['attachment']['source']) for row in page['items'])
  cursor=page['next_cursor']
  if not cursor:break
 assert len(found)==len(set(found))==6
 assert {row[2] for row in found}=={'attachment','screenshot'}


def test_screenshot_filters_and_expired_state(images):
 db,actor,colleague,root,shots,_=images
 result=search(images,keyword='现有')
 assert result['total']==2 and all(row['sender_user_id']==colleague.id for row in result['items'])
 assert search(images,keyword='现有',sender_user_id=actor.id)['total']==0
 json_image=search(images,keyword='富文本')['items'][0]['attachment']
 assert json_image['source']=='screenshot' and json_image['screenshot_reference'].startswith('screenshot://')
 expired=search(images,keyword='过期')['items'][0]['attachment']
 assert expired['available'] is False
 assert search(images,keyword='其他会话')['total']==0
