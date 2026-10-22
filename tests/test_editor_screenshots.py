"""统一截图的授权、到期和去重测试；仅连接隔离内存数据库。"""
from datetime import timedelta
from io import BytesIO
from uuid import UUID,uuid4
import pytest
from PIL import Image as PILImage
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from test_chat_participant_access import environment,project
import editor_screenshot_service as service
from editor_screenshot_models import EditorScreenshot as Image,EditorScreenshotBlob as Blob


def png():
    buf=BytesIO();PILImage.new('RGB',(32,32),'blue').save(buf,'PNG');return buf.getvalue()


def test_owner_grants_expire_and_are_account_scoped(environment):
    db,(owner,member,other)=environment
    saved=service.save_image(db,owner.id,png(),'image/png');uid=UUID(saved['id'])
    assert service.permitted_ids(db,owner.id,{uid})=={uid}
    assert not service.permitted_ids(db,member.id,{uid})
    token,_=service.grant(db,member.id,{uid})
    assert service.permitted_ids(db,member.id,{uid},[token])=={uid}
    assert not service.permitted_ids(db,other.id,{uid},[token])
    from editor_screenshot_models import EditorScreenshotGrant
    db.get(EditorScreenshotGrant,UUID(token)).expires_at=service.now()-timedelta(seconds=1);db.commit()
    assert not service.permitted_ids(db,member.id,{uid},[token])


def test_dedup_retention_promote_and_purge_do_not_delete_business_copy(environment):
    db,(owner,*_)=environment
    chat=service.save_image(db,owner.id,png(),'image/png','chat')
    business=service.save_image(db,owner.id,png(),'image/png')
    assert db.query(Blob).count()==1
    chatrow=db.get(Image,UUID(chat['id']));chatrow.expires_at=service.now()-timedelta(seconds=1);db.commit()
    service.cleanup(db)
    assert db.get(Image,chatrow.id).blob_sha256 is None
    assert db.get(Image,UUID(business['id'])).blob_sha256 and db.query(Blob).count()==1
    promoted=service.save_image(db,owner.id,png(),'image/png','chat')
    service.promote_business_references(db,{UUID(promoted['id'])});db.commit();db.expire_all()
    assert db.get(Image,UUID(promoted['id'])).expires_at is None


def test_only_expired_chat_bytes_removed_and_bad_images_rejected(environment):
    db,(owner,*_)=environment
    saved=service.save_image(db,owner.id,png(),'image/png','chat')
    db.get(Image,UUID(saved['id'])).expires_at=service.now()-timedelta(days=1);db.commit()
    service.cleanup(db)
    assert db.query(Image).count()==1 and db.query(Blob).count()==0
    with pytest.raises(ValueError):service.save_image(db,owner.id,b'notimage','image/png')


def test_chat_image_requires_exact_message_and_participation(environment):
    db,(owner,member,outsider)=environment
    from models import ChatProjectMessage,AnnotationChatMember
    row=project(db,owner)
    db.add(AnnotationChatMember(project_id=row.id,user_id=member.id,last_read_sequence=0))
    image=service.save_image(db,owner.id,png(),'image/png','chat')
    message=ChatProjectMessage(id=uuid4(),annotation_project_id=row.id,sender_user_id=owner.id,sender_name='owner',content=image['reference'],message_type='user',sequence_no=1,created_at=service.now().replace(tzinfo=None))
    db.add(message);db.commit();uid=UUID(image['id'])
    service.check_chat_reference(db,member,uid,message.id)
    with pytest.raises(HTTPException):service.check_chat_reference(db,outsider,uid,message.id)
    with pytest.raises(HTTPException):service.check_chat_reference(db,member,uuid4(),message.id)
    message.created_at=(service.now()-timedelta(days=30)).replace(tzinfo=None);db.commit()
    with pytest.raises(HTTPException) as error:service.check_chat_reference(db,member,uid,message.id)
    assert error.value.status_code==410


def test_middleware_blocks_foreign_reference_and_encoded_reflection(environment,monkeypatch):
    db,(owner,member,*_)=environment
    import editor_screenshot_middleware as middleware
    monkeypatch.setattr(middleware,'engine',db.get_bind())
    monkeypatch.setattr('routers.auth.get_user_from_token_value',lambda session,token:session.get(type(owner),owner.id if token=='owner' else member.id))
    app=FastAPI();app.add_middleware(middleware.EditorScreenshotMiddleware)
    @app.post('/business')
    def echo(body:dict):return body
    @app.get('/business')
    def get():return {'content':reference}
    reference=service.save_image(db,owner.id,png(),'image/png')['reference']
    client=TestClient(app)
    for value in (reference,reference.replace('screenshot','\\u0073creenshot')):
        assert client.post('/business',json={'content':value},headers={'Authorization':'Bearer member'}).status_code==403
    response=client.get('/business',headers={'Authorization':'Bearer member'})
    token=response.headers['x-screenshot-grant']
    assert client.post('/business',json={'content':reference},headers={'Authorization':'Bearer member','X-Screenshot-Grants':token}).status_code==200
    assert client.post('/business',json={'content':reference},headers={'Authorization':'Bearer owner'}).status_code==200
    # 旧版接口即使反射或保存了他人的图片编号，没有服务端签名也不能取得授权。
    reference=reference.split('#')[0]
    assert 'x-screenshot-grant' not in client.get('/business',headers={'Authorization':'Bearer member'}).headers


def test_upload_and_download_endpoints_and_expired_placeholder(environment):
    db,(owner,member,*_)=environment
    from routers.editor_screenshots import router
    from routers.auth import get_current_user
    from database import get_db
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:owner
    client=TestClient(app)
    response=client.post('/editor-screenshots',files={'file':('screen.png',png(),'image/png')},data={'retention':'chat'})
    assert response.status_code==201
    uid=response.json()['id'];path=f'/editor-screenshots/{uid}'
    assert client.get(path).headers['content-type'].startswith('image/')
    app.dependency_overrides[get_current_user]=lambda:member
    assert client.get(path).status_code==403
    token,_=service.grant(db,member.id,{UUID(uid)})
    assert client.get(path,headers={'X-Screenshot-Grants':token}).status_code==200
    db.get(Image,UUID(uid)).expires_at=service.now()-timedelta(seconds=1);db.commit()
    assert client.get(path,headers={'X-Screenshot-Grants':token}).status_code==410


def test_chat_attachments_use_shared_blob_and_workflow_images_are_not_expired(environment):
    db,(owner,*_)=environment
    from chat_screenshot_storage import save_attachment,read_attachment,check_retention
    from models import ChatProjectAttachment
    row=save_attachment(db,owner,png(),'screen.png')
    assert row.storage_name.startswith('screenshot:') and read_attachment(db,row).body
    business=ChatProjectAttachment(id=uuid4(),uploaded_by=owner.id,storage_name='workflow.png',original_name='work.png',content_type='image/png',file_size=100,created_at=(service.now()-timedelta(days=100)).replace(tzinfo=None))
    db.add(business);db.commit()
    check_retention(db,business)
    from models import ChatProjectMessage,ChatProjectMessageAttachment
    from workflow_models import WorkflowHandoverAttachment
    message=ChatProjectMessage(id=uuid4(),sender_user_id=owner.id,sender_name='owner',content='旧交接图片',message_type='user',created_at=(service.now()-timedelta(days=90)).replace(tzinfo=None))
    db.add(message);db.flush()
    db.add_all([ChatProjectMessageAttachment(id=uuid4(),message_id=message.id,attachment_id=business.id),WorkflowHandoverAttachment(id=uuid4(),request_id=uuid4(),attachment_id=business.id)])
    db.commit();check_retention(db,business)


def test_rich_documents_accept_only_authenticated_screenshot_nodes():
    from annotation_notice_schemas import validate_tiptap_document
    from annotation_ops_schemas import ArrangementDailyNoteWrite
    from resource_request_schemas import ResourceRequestDailyNoteWrite
    document={'type':'doc','content':[{'type':'image','attrs':{'src':f'screenshot://{uuid4()}','alt':'截图'}}]}
    assert validate_tiptap_document(document)==document
    ArrangementDailyNoteWrite(content_json=document)
    ResourceRequestDailyNoteWrite(content_json=document)
    document['content'][0]['attrs']['src']='https://example.com/foreign.png'
    with pytest.raises(ValueError):validate_tiptap_document(document)


def test_expired_chat_image_cannot_be_promoted_back_to_permanent(environment):
    db,(owner,*_)=environment
    saved=service.save_image(db,owner.id,png(),'image/png','chat');uid=UUID(saved['id'])
    assert service.valid_references(saved['reference'])=={uid}
    assert not service.valid_references(saved['reference'].split('#')[0])
    row=db.get(Image,uid);row.expires_at=service.now()-timedelta(seconds=1);db.commit()
    service.promote_business_references(db,{uid});db.commit();db.expire_all()
    assert db.get(Image,uid).retention_kind=='chat'
