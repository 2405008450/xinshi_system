"""聊天总结在内存 SQLite 验证，绝不连接业务库或发送真实通知。"""
from datetime import datetime
from uuid import uuid4, UUID
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from test_chat_participant_access import environment  # noqa: F401


@pytest.fixture
def summary_env(environment,monkeypatch):
    db,users=environment
    from models import AppUser,AppNotification
    from department_models import Department
    import resource_issue_service as service
    owner,member,recipient=users
    member.department='IT部';recipient.department='销售'
    unrelated=AppUser(id=uuid4(),username='unrelated',full_name='无关人员',password_hash='disabled',is_active=True)
    inactive=AppUser(id=uuid4(),username='inactive',password_hash='disabled',is_active=False,department='IT部')
    department=Department(name='IT部',aliases=['翻译部']);db.add_all([unrelated,inactive,department]);db.commit()
    db.execute(text('CREATE UNIQUE INDEX uq_summary_manual_test ON resource_development_issue(collected_by,client_request_id)'))
    db.execute(text('CREATE UNIQUE INDEX uq_summary_source_test ON resource_development_issue(source_message_id,category)'));db.commit()
    monkeypatch.setattr(service,'can_collect',lambda db,user:user.id==owner.id)
    monkeypatch.setattr(service,'can_delegate',lambda *args:False)
    monkeypatch.setattr(service,'is_admin',lambda *args:False)
    monkeypatch.setattr(service,'resource_access',lambda db,user:user.id==owner.id)
    def notifications(db,ids,title,content,**kwargs):
        values=[AppNotification(id=uuid4(),recipient_user_id=uid,title=title,content=content,is_read=False,
            notification_type=kwargs['notification_type'],related_project_type=kwargs['related_project_type'],related_entity_id=kwargs['related_entity_id']) for uid in ids]
        db.add_all(values);db.flush();return values
    monkeypatch.setattr('crud.create_notifications_for_users',notifications)
    sent=[]
    monkeypatch.setattr('notification_ws.dispatch_personal_message',lambda uid,payload:sent.append((uid,payload)))
    return db,owner,member,recipient,unrelated,inactive,department,sent


def create(db,owner,category='problem',**summary):
    from resource_issue_schemas import IssueCreate
    import resource_issue_service as service
    payload=IssueCreate(client_request_id=uuid4(),category=category,content='总结测试',summary=summary)
    return service.create_issue(db,owner,payload),payload


@pytest.mark.parametrize('category',['arrangement','request','idea','decision','execution','problem','risk','standard'])
def test_all_eight_categories_are_saved_with_structured_fields(summary_env,category):
    db,owner,*_=summary_env
    data,_=create(db,owner,category,specific_classification='例会')
    assert data['category']==category and data['specific_classification']=='例会'
    assert data['created_at'].endswith('+08:00')


def test_department_and_people_notifications_deduplicate_and_grant_only_selected_access(summary_env):
    from models import AppNotification
    from resource_issue_models import DevelopmentIssueAudience
    import resource_issue_service as service
    from resource_summary_service import commit_notifications
    db,owner,member,recipient,unrelated,inactive,department,sent=summary_env
    data,payload=create(db,owner,'execution',follower_user_ids=[member.id],notify_user_ids=[member.id,recipient.id],notify_department_ids=[department.id],planned_completion_at='2026-10-23T18:00:00+08:00',actual_progress='准备中')
    assert db.query(AppNotification).count()==2
    assert service.get_issue(db,member,UUID(data['id'])) and service.get_issue(db,recipient,UUID(data['id']))
    with pytest.raises(HTTPException):service.get_issue(db,unrelated,UUID(data['id']))
    with pytest.raises(HTTPException):service.get_issue(db,inactive,UUID(data['id']))
    commit_notifications(db)
    assert service.capabilities(db,recipient)['can_enter'] and not service.capabilities(db,recipient)['can_collect']
    assert len(sent)==2 and all(item[1]['notification']['created_at'].endswith('+08:00') for item in sent)
    assert all(item[1]['notification']['notification_type']=='chat_summary' for item in sent)
    again=service.create_issue(db,owner,payload)
    assert again['already_collected'] and db.query(AppNotification).count()==2
    assert db.query(DevelopmentIssueAudience).filter_by(kind='notify_user').count()==2


def test_follower_can_only_update_progress_and_old_revision_is_rejected(summary_env):
    import resource_issue_service as service
    from resource_issue_schemas import IssueUpdate,IssueProgressWrite
    from routers.resource_issues import progress
    db,owner,member,recipient,*_=summary_env
    data,_=create(db,owner,'execution',follower_user_ids=[member.id])
    with pytest.raises(HTTPException) as forbidden:service.update_issue(db,member,UUID(data['id']),IssueUpdate(content='越权修改正文',revision=1))
    assert forbidden.value.status_code==403
    updated=progress(UUID(data['id']),IssueProgressWrite(revision=1,actual_progress='已完成一半'),db,member)
    assert updated['actual_progress']=='已完成一半' and updated['content']=='总结测试' and updated['revision']==2
    with pytest.raises(HTTPException) as stale:progress(UUID(data['id']),IssueProgressWrite(revision=1,actual_progress='旧值'),db,member)
    assert stale.value.status_code==409
    with pytest.raises(ValidationError):IssueProgressWrite(revision=2,actual_progress='进度',content='不允许')


def test_summary_filters_share_scope_department_follower_and_utc8_date_boundaries(summary_env):
    from resource_issue_models import DevelopmentIssue
    from routers.resource_issues import listing
    from business_time import BUSINESS_TIMEZONE
    from uuid import UUID
    db,owner,member,recipient,unrelated,inactive,department,sent=summary_env
    a,_=create(db,owner,'execution',follower_user_ids=[member.id],specific_classification='周会',planned_completion_at='2026-10-23T18:00:00+08:00')
    b,_=create(db,owner,'problem',specific_classification='排查')
    db.get(DevelopmentIssue,UUID(a['id'])).created_at=datetime(2026,10,22,0,0,tzinfo=BUSINESS_TIMEZONE)
    db.get(DevelopmentIssue,UUID(b['id'])).created_at=datetime(2026,10,21,23,59,59,tzinfo=BUSINESS_TIMEZONE);db.flush()
    def query(**filters):return listing(keyword=None,specific_classification=None,skip=0,limit=20,db=db,actor=owner,**filters)
    assert query(category='execution',department_id=department.id,executor_id=member.id,saved_start=datetime(2026,10,22).date(),saved_end=datetime(2026,10,22).date())['total']==1
    assert query(saved_end=datetime(2026,10,21).date())['total']==1
    assert query(executor_id=unrelated.id)['total']==0


def test_task_fields_timezone_and_targets_are_validated(summary_env):
    from resource_issue_schemas import SummaryFields
    db,owner,member,recipient,unrelated,inactive,*_=summary_env
    with pytest.raises(ValidationError):SummaryFields(planned_completion_at='2026-10-23T18:00:00')
    assert SummaryFields(planned_completion_at='2026-10-23T10:00:00Z').planned_completion_at.isoformat()=='2026-10-23T18:00:00+08:00'
    with pytest.raises(HTTPException):create(db,owner,'problem',follower_user_ids=[member.id])
    with pytest.raises(HTTPException):create(db,owner,'execution',follower_user_ids=[inactive.id])
