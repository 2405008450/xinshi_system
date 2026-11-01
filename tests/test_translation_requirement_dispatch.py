"""项目设置、共享安排和双回执；仅使用内存 SQLite。"""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect

from tests.test_translation_simple_requirements import context, payload
from tests.test_chat_participant_access import environment
from models import AppNotification, TranslationProject
from department_models import DepartmentMember
import translation_simple_requirements as simple
import translation_requirement_dispatch as service


def settings(row, **values):
    return service.ProjectSettings(request_id=uuid4(),expected_updated_at=row.updated_at,**values)


def dispatch(row, member, **values):
    return service.DispatchCreate(**(dict(request_id=uuid4(),expected_updated_at=row.updated_at,
        recipient_ids=[member.id],content='  按客户要求完成术语核对  ')|values))


def test_settings_deadline_status_audit_version_and_idempotent_retry(context):
    db,owner,member,_,row,_=context
    request=settings(row,project_status='arranged',customer_deadline_time='2026-11-02T02:30:00Z')
    result=service.save_settings(db,row.id,request,owner)
    assert row.project_status=='arranged' and row.customer_deadline_time==datetime(2026,11,2,10,30)
    assert result['customer_deadline_time']=='2026-11-02T10:30:00+08:00'
    audit=db.query(service.RequirementEvent).one()
    assert audit.actor_user_id==owner.id and audit.payload['before']['project_status']=='confirmed'
    assert audit.payload['after']['project_status']=='arranged'
    assert service.save_settings(db,row.id,request,owner)['project_updated_at']==result['project_updated_at']
    assert db.query(service.RequirementEvent).count()==1
    # 重试返回原保存版本，不能让旧表单接受别人后续修改后的版本。
    row.updated_at+=timedelta(seconds=1);db.commit()
    again=service.save_settings(db,row.id,request,owner)
    assert again['project_updated_at']==result['project_updated_at']
    with pytest.raises(HTTPException):service.save_settings(db,row.id,request.model_copy(update={'project_status':'paused'}),owner)
    with pytest.raises(HTTPException) as error:
        service.save_settings(db,row.id,settings(row,project_status='paused').model_copy(update={'expected_updated_at':None}),owner)
    assert error.value.status_code==409
    service.save_settings(db,row.id,settings(row,customer_deadline_time=None),owner)
    assert row.customer_deadline_time is None
    assert simple.list_requirements(db,row.id)['customer_deadline_time'] is None


@pytest.mark.parametrize('change',[{},dict(project_status=None),dict(project_status='fake')])
def test_settings_invalid_payload(context,change):
    _,_,_,_,row,_=context
    with pytest.raises(ValidationError):settings(row,**change)


def test_dispatch_snapshot_shared_text_multi_recipients_and_retry(context):
    db,owner,member,other,row,dept=context
    db.add(DepartmentMember(department_id=dept.id,user_id=other.id,position=''));db.commit()
    note=simple.create_requirement(db,row.id,payload(row,member),owner)['item']
    row.customer_deadline_time=datetime(2026,11,3,18);db.commit()
    request=dispatch(row,member,requirement_id=note['id'],recipient_ids=[member.id,other.id])
    result=service.create_dispatch(db,row.id,request,owner)
    assert result['content']=='按客户要求完成术语核对'
    assert result['requirement_snapshot']['original_text']=='请确认术语'
    assert result['customer_deadline_time']=='2026-11-03T18:00:00+08:00'
    assert len(result['recipients'])==2 and result['created_at'].endswith('+08:00')
    assert db.query(AppNotification).filter_by(notification_type='translation_simple_dispatch').count()==2
    assert service.create_dispatch(db,row.id,request,owner)['id']==result['id']
    assert db.query(service.RequirementDispatch).count()==1
    with pytest.raises(HTTPException):service.create_dispatch(db,row.id,request.model_copy(update={'content':'修改同一发送请求'}),owner)
    row.customer_deadline_time=datetime(2026,11,4,20);db.commit()
    assert service.dispatch_detail(db,result['id'],member)['customer_deadline_time']=='2026-11-03T18:00:00+08:00'
    assert service.dispatch_detail(db,result['id'],member)['current_customer_deadline_time']=='2026-11-04T20:00:00+08:00'


def test_dispatch_recipient_scope_and_cross_project_requirement_rejected(context):
    db,owner,member,outsider,row,_=context
    for changed in (dict(recipient_ids=[outsider.id]),dict(requirement_id=uuid4()),dict(expected_updated_at=None)):
        with pytest.raises(HTTPException):service.create_dispatch(db,row.id,dispatch(row,member,**changed),owner)
    assert db.query(service.RequirementDispatch).count()==0
    other=TranslationProject(id=uuid4(),order_no='TP-OTHER',project_name='另一项目.docx',project_status='confirmed')
    db.add(other);db.commit()
    note=simple.create_requirement(db,other.id,payload(other,member),owner)['item']
    with pytest.raises(HTTPException):service.create_dispatch(db,row.id,dispatch(row,member,requirement_id=note['id']),owner)
    for values in (dict(content='  '),dict(recipient_ids=[]),dict(recipient_ids=[member.id,member.id])):
        with pytest.raises(ValidationError):dispatch(row,member,**values)


def test_two_receipts_self_only_ordered_idempotent_and_sender_notification(context,monkeypatch):
    db,owner,member,outsider,row,_=context
    monkeypatch.setattr('permission_service.user_has_permission',lambda *args:False)
    record=service.create_dispatch(db,row.id,dispatch(row,member),owner)
    for actor in (owner,outsider):
        with pytest.raises(HTTPException):service.dispatch_receipt(db,record['id'],'received',service.ReceiptInput(reply='收到'),actor)
    with pytest.raises(HTTPException):service.dispatch_detail(db,record['id'],outsider)
    with pytest.raises(HTTPException) as early:service.dispatch_receipt(db,record['id'],'completed',service.ReceiptInput(reply='已完成'),member)
    assert early.value.status_code==409
    first=service.dispatch_receipt(db,record['id'],'received',service.ReceiptInput(reply='收到，处理中'),member)
    assert first['can_reply'] is False and first['can_complete'] is True
    second=service.dispatch_receipt(db,record['id'],'completed',service.ReceiptInput(reply='已完成术语核对'),member)
    assert second['can_complete'] is False and second['my_completed_at'].endswith('+08:00')
    assert second['recipients'][0]['completed_reply']=='已完成术语核对'
    service.dispatch_receipt(db,record['id'],'completed',service.ReceiptInput(reply='重复点击'),member)
    assert db.query(service.RequirementEvent).count()==2
    assert db.query(AppNotification).filter_by(notification_type='translation_simple_dispatch_receipt',recipient_user_id=owner.id).count()==2
    assert service.dispatch_detail(db,record['id'],owner)['content']==record['content']
    assert service.project_activity(db,row.id,0,10)['items'][0]['recipients'][0]['completed_at']
    from schemas import NotificationResponse
    original=db.query(AppNotification).filter_by(notification_type='translation_simple_dispatch').one()
    assert NotificationResponse.model_validate(original).model_dump(mode='json')['read_at'].endswith('+08:00')


def test_existing_requirement_also_supports_completed_receipt(context):
    db,owner,member,outsider,row,_=context
    note=simple.create_requirement(db,row.id,payload(row,member,saved_status='confirmed'),owner)['item']
    assert row.project_status=='confirmed'
    with pytest.raises(HTTPException):service.complete_requirement(db,note['id'],service.ReceiptInput(reply='已完成'),outsider)
    with pytest.raises(HTTPException):service.complete_requirement(db,note['id'],service.ReceiptInput(reply='已完成'),member)
    simple.receive(db,note['id'],simple.RequirementReply(),member)
    result=service.complete_requirement(db,note['id'],service.ReceiptInput(reply='已完成'),member)
    assert result['my_completed_at'] and not result['can_complete']
    service.complete_requirement(db,note['id'],service.ReceiptInput(reply='重试'),member)
    assert db.query(service.RequirementEvent).filter_by(subject_kind='requirement').count()==1
    assert simple.list_requirements(db,row.id)['items'][0]['recipients'][0]['completed_reply']=='已完成'


def test_permissions_recipient_can_reply_without_project_read_and_readers_see_shared_text(context,monkeypatch):
    db,owner,member,outsider,row,_=context
    record=service.create_dispatch(db,row.id,dispatch(row,member),owner)
    from database import get_db
    from routers.auth import get_current_user
    app=FastAPI();app.include_router(service.router)
    app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:member
    monkeypatch.setattr('routers.auth.user_has_permission',lambda *args:False)
    client=TestClient(app)
    assert client.get(f"/translation-simple-requirements/dispatches/{record['id']}").status_code==200
    assert client.post(f"/translation-simple-requirements/dispatches/{record['id']}/received",json={'reply':'收到'}).status_code==200
    assert client.get(f'/translation-simple-requirements/projects/{row.id}/dispatches').status_code==403
    assert client.patch(f'/translation-simple-requirements/projects/{row.id}/settings',json=settings(row,project_status='paused').model_dump(mode='json')).status_code==403
    monkeypatch.setattr('permission_service.user_has_permission',lambda db,user_id,code:code=='projects:read')
    assert service.dispatch_detail(db,record['id'],outsider)['content']==record['content']
    assert service.dispatch_detail(db,record['id'],outsider)['is_recipient'] is False


def test_commit_failure_rolls_back_dispatch_and_notification(context,monkeypatch):
    db,owner,member,_,row,_=context
    def fail():raise RuntimeError('isolated simulated commit failure')
    with monkeypatch.context() as patch:
        patch.setattr(db,'commit',fail)
        with pytest.raises(RuntimeError):service.create_dispatch(db,row.id,dispatch(row,member),owner)
    db.rollback()
    assert db.query(service.RequirementDispatch).count()==0 and db.query(AppNotification).count()==0


def test_repeatable_migration_creates_only_three_new_tables():
    import main
    from tools.apply_translation_dispatch_migration import apply_migration,TABLES
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        apply_migration(connection);apply_migration(connection)
        assert set(inspect(connection).get_table_names())==set(TABLES)
    engine.dispose()
