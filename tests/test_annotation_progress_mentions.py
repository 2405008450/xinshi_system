from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment, project


def test_shared_defaults_and_department_expansion_deduplicate_and_exclude_sender(environment, monkeypatch):
    db, (owner, member, outsider) = environment
    from department_models import Department
    from annotation_progress_chat import MentionSelection, save_defaults, options, resolve_users
    monkeypatch.setattr('permission_service.user_has_permission', lambda db, uid, permission: uid == owner.id)
    dept = Department(id=uuid4(), name='项目部', aliases=['旧项目部'])
    db.add(dept);owner.department='项目部';member.department='旧项目部';db.commit()
    selection=MentionSelection(user_ids=[owner.id, member.id, member.id],department_ids=[dept.id,dept.id])
    save_defaults(db, owner, selection)
    assert set(options(db, outsider)['user_ids']) == {str(owner.id),str(member.id)}
    assert resolve_users(db, selection, owner)==[member.id]
    with pytest.raises(HTTPException):save_defaults(db, outsider, selection)
    member.is_active=False;db.commit()
    with pytest.raises(HTTPException):resolve_users(db, selection, owner)


def test_customer_progress_and_message_share_transaction_and_exact_child_id(environment, monkeypatch):
    db,(owner,member,outsider)=environment
    import annotation_chat_service as chat
    from models import AnnotationChatMember, ChatProjectMessage
    from annotation_customer_progress_models import AnnotationCustomerProgress
    from annotation_customer_progress_service import create_customer_progress
    from annotation_customer_progress_schemas import CustomerProgressWrite
    from annotation_progress_chat import ProgressChatDelivery
    child=project(db,owner,'AP-261007-001.001')
    db.add(AnnotationChatMember(project_id=child.id,user_id=owner.id,last_read_sequence=0,following=True));db.commit()
    seen=[]
    def send(db, project_id, actor, payload, *, commit=True, max_mentions=20):
        assert not commit and db.in_transaction()
        assert max_mentions==2000
        assert db.query(AnnotationCustomerProgress).filter_by(project_id=child.id).count()==1
        assert project_id==child.id and payload.mentioned_user_ids==[member.id]
        seen.append(payload)
        db.add(ChatProjectMessage(id=uuid4(),annotation_project_id=project_id,sender_user_id=actor.id,sender_name='owner',content=payload.content,message_type='user',sequence_no=1))
    monkeypatch.setattr(chat,'send_message',send)
    payload=CustomerProgressWrite(change_note='隔离测试进度',effective_on=datetime(2026,10,22,14,0,tzinfo=timezone(timedelta(hours=8))),chat_delivery=ProgressChatDelivery(send_to_chat=True,user_ids=[member.id,owner.id]))
    create_customer_progress(db,child.id,payload,owner.id)
    assert len(seen)==1 and seen[0].content=='隔离测试进度'
    assert db.query(ChatProjectMessage).filter_by(annotation_project_id=child.id).count()==1
    assert db.query(AnnotationCustomerProgress).count()==1


def test_send_failure_rolls_back_progress_and_save_only_does_not_send(environment, monkeypatch):
    db,(owner,*_)=environment
    from models import AnnotationChatMember
    from annotation_customer_progress_models import AnnotationCustomerProgress
    from annotation_customer_progress_service import create_customer_progress
    from annotation_customer_progress_schemas import CustomerProgressWrite
    from annotation_progress_chat import ProgressChatDelivery
    row=project(db,owner)
    db.add(AnnotationChatMember(project_id=row.id,user_id=owner.id,last_read_sequence=0,following=True));db.commit()
    def fail(*args,**kwargs):raise HTTPException(409,'消息写入失败')
    monkeypatch.setattr('annotation_chat_service.send_message',fail)
    with pytest.raises(HTTPException):
        create_customer_progress(db,row.id,CustomerProgressWrite(change_note='失败测试',chat_delivery=ProgressChatDelivery(send_to_chat=True)),owner.id)
    db.rollback()
    assert db.query(AnnotationCustomerProgress).count()==0
    create_customer_progress(db,row.id,CustomerProgressWrite(change_note='只保存',chat_delivery=ProgressChatDelivery(send_to_chat=False)),owner.id)
    assert db.query(AnnotationCustomerProgress).count()==1


def test_project_progress_delivery_runs_before_commit_without_changing_status(environment, monkeypatch):
    db,(owner,*_)=environment
    import annotation_service as service
    from annotation_ops_models import AnnotationProjectStatusHistory
    from annotation_progress_chat import ProgressChatDelivery
    row=project(db,owner);row.project_status='initial_consultation';row.priority='medium'
    row.status_effective_on=row.created_at=row.updated_at=datetime(2026,10,22,14,0);db.commit()
    monkeypatch.setattr(service,'_lock_annotation_order_numbers',lambda db:None)
    monkeypatch.setattr(service,'get_annotation_project',lambda db,uid:db.get(type(row),uid))
    calls=[]
    def enqueue(db,uid,actor,delivery,**details):
        assert db.in_transaction() and delivery.send_to_chat
        assert uid==row.id and actor==owner.id and details['track']=='project'
        for record in db.new:
            if isinstance(record,AnnotationProjectStatusHistory):record.id=uuid4()
        calls.append(details)
    monkeypatch.setattr('annotation_progress_chat.enqueue',enqueue)
    now=datetime(2026,10,22,15,0)
    service.update_annotation_project_status(db,row.id,row.project_status,now,'项目进度测试',owner.id,True,ProgressChatDelivery(send_to_chat=True))
    assert len(calls)==1 and row.project_status=='initial_consultation'
    assert db.query(AnnotationProjectStatusHistory).filter_by(project_id=row.id,entry_kind='progress').count()==1


def test_progress_can_mention_company_wide_without_changing_normal_message_limit():
    from project_chat_crud import _normalize_mentioned_user_ids
    sender=uuid4();ids=[uuid4() for _ in range(60)]
    with pytest.raises(ValueError):_normalize_mentioned_user_ids(sender,mentioned_user_ids=ids)
    assert _normalize_mentioned_user_ids(sender,mentioned_user_ids=ids+[sender],max_mentions=2000)==ids
