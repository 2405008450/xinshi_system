"""开发笔记权限、附件、追加版本、冲突与迁移；仅使用内存SQLite。"""
from io import BytesIO
from uuid import uuid4
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from test_chat_participant_access import environment
import development_notes as notes


@pytest.fixture
def setup(environment,monkeypatch):
    db,users=environment
    owner,member,outsider=users
    monkeypatch.setattr(notes,'ACCOUNTS',{owner.id:(owner.username,'赵震锋'),member.id:(member.username,'黄运坚')})
    return db,users


def doc(text='开发笔记',src=None):
    content=[{'type':'paragraph','content':[{'type':'text','text':text,'marks':[{'type':'bold'},{'type':'textColor','attrs':{'color':'#dc2626'}},{'type':'underline','attrs':{'color':'#111827'}},{'type':'highlight','attrs':{'color':'#fff59d'}}]}]}]
    if src:content.append({'type':'image','attrs':{'src':src}})
    return {'type':'doc','content':content}


def block(db,user):return notes.create(notes.CreateBlock(request_id=uuid4()),db,user)
def write(revision=0,**extra):return notes.SaveBlock(request_id=uuid4(),revision=revision,title='开发记录',document=doc(),**extra)


def test_exact_account_access_own_area_and_untrusted_names(setup):
    db,(a,b,other)=setup
    item=block(db,a)
    assert notes.access(a)=={'allowed':True}
    other.full_name='赵震锋'
    assert not notes.allowed(other)
    with pytest.raises(HTTPException) as error:notes.listing(db,other)
    assert error.value.status_code==403
    result=notes.listing(db,b)
    assert [owner['can_edit'] for owner in result['owners']]==[False,True]
    with pytest.raises(HTTPException) as error:notes.save_block(db,b,item['id'],write())
    assert error.value.status_code==403
    a.is_active=False
    assert not notes.allowed(a)
    with pytest.raises(HTTPException):notes.history(item['id'],db=db,user=a)


def test_save_snapshots_idempotency_and_conflicts(setup):
    db,(a,b,_)=setup
    item=block(db,a)
    first=write();saved=notes.save_block(db,a,item['id'],first)
    assert saved['revision']==1 and saved['saved_at'].endswith('+08:00')
    assert notes.save_block(db,a,item['id'],first)['revision']==1
    second=write(1);second.document=doc('第二次说明')
    notes.save_block(db,a,item['id'],second)
    records=notes.history(item['id'],skip=0,limit=20,db=db,user=b)
    assert records['total']==2 and [row['revision'] for row in records['items']]==[2,1]
    assert records['items'][1]['document']==doc()
    with pytest.raises(HTTPException) as conflict:notes.save_block(db,a,item['id'],write())
    assert conflict.value.status_code==409
    assert notes.history(item['id'],skip=0,limit=20,db=db,user=a)['total']==2


def test_files_images_history_and_http_permission(setup):
    db,(a,b,other)=setup
    item=block(db,a);second=block(db,a)
    app=FastAPI();app.include_router(notes.router)
    app.dependency_overrides[notes.get_db]=lambda:db
    app.dependency_overrides[notes.get_current_user]=lambda:a
    client=TestClient(app)
    image=BytesIO();Image.new('RGB',(3,3),'red').save(image,format='PNG')
    uploaded=client.post(f"/development-notes/blocks/{item['id']}/files",files={'file':('截图.png',image.getvalue(),'image/png')})
    assert uploaded.status_code==201,uploaded.text
    pic=uploaded.json()
    file=client.post(f"/development-notes/blocks/{item['id']}/files",files={'file':('需求.txt',b'notes','text/plain')}).json()
    payload=write(attachment_ids=[file['id']]);payload.document=doc(src=pic['src'])
    notes.save_block(db,a,item['id'],payload)
    assert notes.listing(db,b)['owners'][0]['blocks'][0]['files'][0]['filename']=='需求.txt'
    app.dependency_overrides[notes.get_current_user]=lambda:b
    read=client.get('/development-notes/files/'+pic['id'])
    assert read.status_code==200 and read.headers['content-type']=='image/png'
    assert client.post(f"/development-notes/blocks/{item['id']}/files",files={'file':('伪造.txt',b'no')}).status_code==403
    app.dependency_overrides[notes.get_current_user]=lambda:other
    assert client.get('/development-notes/files/'+pic['id']).status_code==403
    assert client.get(f"/development-notes/blocks/{item['id']}/history").status_code==403
    with pytest.raises(HTTPException):notes.save_block(db,a,second['id'],write(attachment_ids=[file['id']]))
    for source in ['https://example.com/private.png','javascript:alert(1)']:
        with pytest.raises(HTTPException):notes.validate_document(doc(src=source))


def test_migration_is_idempotent(setup):
    db,_=setup
    from tools.apply_development_notes_migration import apply_migration
    for table in reversed(notes.TABLES):table.drop(db.connection())
    apply_migration(db.connection());apply_migration(db.connection())
    db.commit()
    assert db.query(notes.DevelopmentNoteBlock).count()==0
