"""报告沟通接收范围、通知和逐项权限；仅使用隔离 SQLite。"""
from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_work_report_access import configure_user,report
import work_report_access as access
import work_report_collaboration as communication
import work_report_feedback_recipients as recipients
from models import AppNotification


def setup_report(environment):
    db,(owner,receiver,author)=environment
    configure_user(db,owner)
    access.save_rule(db,owner,access.AccessRuleWrite(name='报告查看',viewer_ids=[owner.id],sender_ids=[author.id]))
    row=report(db,author,date(2026,11,26))
    from task_models import DailyReportItem
    other=DailyReportItem(id=uuid4(),report_id=row.id,source_type='manual',task_type='非项目工作',progress_content='另一个工作项',duration_minutes=10,sort_order=1)
    row.items.append(other);db.commit()
    return db,owner,receiver,author,row,other


def test_targeted_recipient_gets_only_selected_thread_and_can_reply(environment):
    db,owner,receiver,author,row,other=setup_report(environment)
    communication.add_feedback(db,owner,row.id,communication.FeedbackWrite(item_key=other.id,content='另一项默认沟通'))
    key=communication.item_key(row.items[0])
    communication.add_feedback(db,owner,row.id,communication.FeedbackWrite(item_key=key,content='请协助',recipient_mode='people',recipient_ids=[receiver.id]))
    assert access.access_context(db,receiver)['can_receive']
    assert communication.feedback_inbox(db,receiver)['total']==1
    messages=communication.feedback_rows(db,receiver,row.id)['items']
    assert [message['content'] for message in messages]==['请协助']
    assert messages[0]['created_at'].utcoffset().total_seconds()==28800
    assert db.query(AppNotification).filter_by(recipient_user_id=receiver.id,notification_type='work_report_feedback').count()==1
    with pytest.raises(HTTPException):access.received_report(db,receiver,row.id)
    with pytest.raises(HTTPException):communication.revision_history(db,receiver,row.id)
    with pytest.raises(HTTPException):communication.add_feedback(db,receiver,row.id,communication.FeedbackWrite(item_key=other.id,content='越权回复'))
    communication.add_feedback(db,receiver,row.id,communication.FeedbackWrite(item_key=key,content='已收到'))
    assert [m['content'] for m in communication.feedback_rows(db,receiver,row.id)['items']]==['请协助','已收到']
    assert db.query(AppNotification).filter_by(recipient_user_id=owner.id,notification_type='work_report_feedback').count()==1


def test_all_and_department_recipients_are_resolved_from_active_directory(environment):
    db,owner,receiver,author,row,_=setup_report(environment)
    from department_models import Department,DepartmentMember
    department=Department(id=uuid4(),name='测试部门',aliases=['旧部门'],revision=1)
    db.add(department);db.add(DepartmentMember(department_id=department.id,user_id=receiver.id,position='成员'));db.commit()
    key=communication.item_key(row.items[0])
    first=communication.add_feedback(db,owner,row.id,communication.FeedbackWrite(item_key=key,content='按部门发送',recipient_mode='departments',department_ids=[department.id]))
    ids={uid for uid, in db.query(recipients.ReportFeedbackRecipient.user_id).filter_by(feedback_id=first['id'])}
    assert ids=={receiver.id,author.id}
    second=communication.add_feedback(db,owner,row.id,communication.FeedbackWrite(item_key=key,content='全员同步',recipient_mode='all'))
    assert db.query(recipients.ReportFeedbackRecipient).filter_by(feedback_id=second['id']).count()==3
    assert db.query(AppNotification).filter_by(recipient_user_id=owner.id).count()==0
    assert len(recipients.directory(db,receiver,row.id)['people'])==3
    receiver.is_active=False;db.commit()
    before=db.query(communication.ReportFeedback).count()
    with pytest.raises(HTTPException):communication.add_feedback(db,owner,row.id,communication.FeedbackWrite(item_key=key,content='停用人员',recipient_mode='people',recipient_ids=[receiver.id]))
    assert db.query(communication.ReportFeedback).count()==before
    with pytest.raises(HTTPException):communication.feedback_rows(db,receiver,row.id)


def test_recipient_migration_is_repeatable_and_no_implicit_schema_changes(environment):
    from tools.apply_work_report_feedback_recipients_migration import apply_migration
    db,_=environment
    recipients.ReportFeedbackRecipient.__table__.drop(db.connection())
    assert not recipients.ready(db)
    apply_migration(db.connection());apply_migration(db.connection())
    assert recipients.ready(db)
    assert db.query(recipients.ReportFeedbackRecipient).count()==0
