from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from test_chat_participant_access import environment, project
from test_chat_mentions_all import chat_env


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


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('track', ['creation', 'customer'])
@pytest.mark.parametrize('by_department', [False, True])
def test_delivery_adds_selected_recipients_before_member_only_message_validation(chat_env, monkeypatch, existing, track, by_department):
    db, (owner, member, outsider) = chat_env
    from fastapi import HTTPException
    from models import AnnotationChatMember, ChatProjectMessage, ChatProjectMention
    from department_models import Department
    import annotation_progress_chat as delivery_service
    import chat_mention_recipients as recipients
    from annotation_creation_chat import send_creation
    row = project(db, owner, 'AP-CREATION-DELIVERY')
    if existing:
        db.add(AnnotationChatMember(project_id=row.id, user_id=owner.id, last_read_sequence=0))
        db.add(ChatProjectMessage(annotation_project_id=row.id, sender_user_id=owner.id, sender_name='owner', content='历史消息', message_type='user', sequence_no=7))
        db.commit()
    selection = dict(user_ids=[owner.id, member.id, member.id])
    if by_department:
        dept = Department(id=uuid4(), name='通知测试部门', aliases=[])
        db.add(dept); member.department = dept.name; db.commit()
        selection = dict(department_ids=[dept.id])
    actual_resolve = recipients.resolve_mentions
    def member_only(db, kind, cid, sender, explicit=(), mention_all=False):
        # 复现此前收紧 @ 后的成员校验：业务发送应先显式邀请通知对象。
        from chat_access_service import member_ids
        if not (set(explicit) - {sender.id}) <= member_ids(db, kind, cid):
            raise HTTPException(422, '只能提及当前会话成员')
        return actual_resolve(db, kind, cid, sender, explicit, mention_all)
    monkeypatch.setattr(recipients, 'resolve_mentions', member_only)
    delivery = delivery_service.ProgressChatDelivery(send_to_chat=True, **selection)
    if track == 'creation':
        send_creation(db, row, owner.id, delivery)
    else:
        delivery_service.enqueue(db, row.id, owner.id, delivery, track=track, note='项目进度', effective_on=None)
    db.flush()
    message = db.query(ChatProjectMessage).filter_by(annotation_project_id=row.id).order_by(ChatProjectMessage.sequence_no.desc()).first()
    if track == 'creation':
        assert message.content_json['type'] == 'annotation_creation'
    else:
        assert message.content == '项目进度'
    assert {uid for uid, in db.query(AnnotationChatMember.user_id).filter_by(project_id=row.id)} == {owner.id, member.id}
    membership = db.get(AnnotationChatMember, (row.id, member.id))
    assert membership.last_read_sequence == (7 if existing else 0)
    assert db.query(ChatProjectMention).filter_by(message_id=message.id, mentioned_user_id=member.id).count() == 1
    # 送会话继续与保存业务数据共用事务，不能在发送函数中提前提交。
    db.rollback()
    assert db.get(AnnotationChatMember, (row.id, member.id)) is None


def test_creation_delivery_failure_rolls_back_new_project_and_invited_members(chat_env, monkeypatch):
    db, (owner, member, _) = chat_env
    from annotation_models import AnnotationProject
    from models import AnnotationChatMember, ChatProjectMessage, AppNotification
    from annotation_creation_chat import send_creation
    from annotation_progress_chat import ProgressChatDelivery
    import annotation_chat_service as chat
    row = AnnotationProject(id=uuid4(), order_no='AP-SAVE-ROLLBACK', project_name='隔离新增项目', created_by=owner.id)
    db.add(row); db.flush(); project_id = row.id
    def fail_send(session, pid, user, payload, **kwargs):
        assert session.get(AnnotationChatMember, (pid, member.id)) is not None
        assert kwargs['commit'] is False
        raise RuntimeError('隔离测试：发送失败')
    monkeypatch.setattr(chat, 'send_message', fail_send)
    with pytest.raises(RuntimeError):
        send_creation(db, row, owner.id, ProgressChatDelivery(send_to_chat=True, user_ids=[member.id]))
    db.rollback()
    assert db.get(AnnotationProject, project_id) is None
    assert db.query(AnnotationChatMember).count() == 0
    assert db.query(ChatProjectMessage).count() == 0
    assert db.query(AppNotification).count() == 0


def test_save_without_delivery_does_not_create_members_or_messages(chat_env):
    db, (owner, member, _) = chat_env
    from models import AnnotationChatMember, ChatProjectMessage
    from annotation_creation_chat import send_creation
    from annotation_progress_chat import ProgressChatDelivery
    row = project(db, owner)
    send_creation(db, row, owner.id, ProgressChatDelivery(send_to_chat=False, user_ids=[member.id]))
    assert db.query(AnnotationChatMember).count() == 0
    assert db.query(ChatProjectMessage).count() == 0


def test_delivery_cannot_bypass_existing_conversation_membership(chat_env):
    db, (owner, member, outsider) = chat_env
    from fastapi import HTTPException
    from models import AnnotationChatMember, ChatProjectMessage
    from annotation_progress_chat import enqueue, ProgressChatDelivery
    row = project(db, owner)
    db.add(AnnotationChatMember(project_id=row.id, user_id=outsider.id, last_read_sequence=0)); db.commit()
    with pytest.raises(HTTPException) as error:
        enqueue(db, row.id, owner.id, ProgressChatDelivery(send_to_chat=True, user_ids=[member.id]), track='creation', note='隔离测试', effective_on=None)
    assert error.value.status_code == 404
    assert db.get(AnnotationChatMember, (row.id, owner.id)) is None
    assert db.get(AnnotationChatMember, (row.id, member.id)) is None
    assert db.query(ChatProjectMessage).count() == 0
