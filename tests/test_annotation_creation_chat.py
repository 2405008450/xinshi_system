from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from test_chat_participant_access import environment, project


def test_creation_defaults_start_with_zhao_and_are_separate_from_progress(environment,monkeypatch):
    db,(owner,member,outsider)=environment
    from annotation_progress_chat import options,save_defaults,MentionSelection
    monkeypatch.setattr('permission_service.user_has_permission',lambda db,uid,p:uid==owner.id)
    member.full_name='赵震锋';db.commit()
    assert options(db,owner,'creation')['automatic_user_ids']==[member.id]
    save_defaults(db,owner,MentionSelection(user_ids=[outsider.id]),'progress')
    save_defaults(db,owner,MentionSelection(user_ids=[member.id,owner.id]),'creation')
    assert options(db,owner,'creation')['automatic_user_ids']==[]
    assert set(options(db,owner,'creation')['user_ids'])=={str(member.id),str(owner.id)}
    assert options(db,owner,'progress')['user_ids']==[str(outsider.id)]


def test_task_images_are_owned_images_and_bind_to_exact_order(environment):
    db,(owner,member,*_)=environment
    from annotation_material_models import AnnotationMaterialUpload as Upload,AnnotationMaterialFile as Material
    from annotation_task_images import apply_images,image_rows,chat_attachments
    from models import ChatProjectAttachment
    row=project(db,owner,'AP-261007-001.001')
    upload=Upload(id=uuid4(),uploaded_by=owner.id,uploader_name='owner',original_name='task.png',storage_key=uuid4().hex,file_size=20,content_type='image/png',sha256='0'*64,created_at=datetime.utcnow(),expires_at=datetime.utcnow()+timedelta(days=1))
    db.add(upload);db.commit()
    with pytest.raises(ValueError):apply_images(db,row,[upload.id],member.id)
    db.rollback()
    apply_images(db,row,[upload.id,upload.id],owner.id);db.commit()
    assert row.task_image_upload_ids==[str(upload.id)]
    assert len(image_rows(db,row))==1 and db.query(Material).filter_by(project_id=row.id).count()==1
    apply_images(db,row,[upload.id],member.id)  # 已归属本项目的截图在编辑时可以保留。
    attachment_ids=chat_attachments(db,row,owner.id)
    attachment=db.get(ChatProjectAttachment,attachment_ids[0])
    assert attachment.annotation_project_id==row.id and attachment.storage_name.startswith('material:')
    other=project(db,owner,'AP-261007-002')
    with pytest.raises(ValueError):apply_images(db,other,[upload.id],owner.id)


def test_creation_card_has_all_nine_fields_and_sends_images_to_same_project(monkeypatch):
    from annotation_creation_chat import creation_card,send_creation
    from annotation_progress_chat import ProgressChatDelivery
    row=SimpleNamespace(id=uuid4(),order_no='AP-261022-001',project_name='示例项目',project_types=['audio_annotation'],project_status='trial_preparation',client_short_name='示例客户',language_items_display='中文→英语',task_submitted_at=None,customer_price_summary='¥0.5/条',task_description='任务文字',created_at=datetime(2026,10,22,15))
    card=creation_card(row)
    assert [f['label'] for f in card['fields']]==['订单号','项目名称','项目类型','项目状态/进度','客户简称','语言方向','任务提交时间','客户单价','具体任务']
    assert card['fields'][-1]['value']=='任务文字'
    calls=[];image=uuid4()
    monkeypatch.setattr('annotation_creation_chat.enqueue',lambda *args,**kwargs:calls.append((args,kwargs)))
    monkeypatch.setattr('annotation_creation_chat.chat_attachments',lambda *args:[image])
    send_creation(None,row,uuid4(),ProgressChatDelivery(send_to_chat=False));assert calls==[]
    send_creation(None,row,uuid4(),ProgressChatDelivery(send_to_chat=True))
    assert calls[0][0][1]==row.id and calls[0][1]['attachment_ids']==[image]
    assert calls[0][1]['content_json']==card
    assert '客户单价：¥0.5/条' in calls[0][1]['note']
