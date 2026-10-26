"""查看、逐项沟通、法定工作日统计和一次修订：内存数据库隔离回归。"""
from datetime import date,datetime
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_work_report_access import configure_user,report
import work_report_access as access
import work_report_collaboration as collaboration
from chat_time import BUSINESS_TIMEZONE


def rule(db,owner,viewer,sender):
    configure_user(db,owner)
    access.save_rule(db,owner,access.AccessRuleWrite(name='测试查看范围',viewer_ids=[viewer.id],sender_ids=[sender.id]))


def test_workday_calendar_includes_makeup_and_excludes_holidays():
    from work_report_calendar import is_workday,period_bounds
    assert is_workday(date(2026,10,10))
    assert not is_workday(date(2026,10,1))
    assert not is_workday(date(2026,10,24))
    assert is_workday(date(2026,9,20))
    assert not is_workday(date(2025,1,29))
    with pytest.raises(HTTPException):is_workday(date(2027,1,1))
    assert period_bounds(date(2026,10,24),'week')==(date(2026,10,19),date(2026,10,25))


def test_feedback_multiple_replies_author_and_lulu_oversight(environment):
    db,(owner,viewer,sender)=environment
    rule(db,owner,viewer,sender)
    row=report(db,sender,date(2026,10,23));item=row.items[0]
    key=collaboration.item_key(item)
    with pytest.raises(HTTPException):collaboration.add_feedback(db,sender,row.id,collaboration.FeedbackWrite(item_key=key,content='自行发起'))
    collaboration.add_feedback(db,viewer,row.id,collaboration.FeedbackWrite(item_key=key,content='请补充客户需求'))
    collaboration.add_feedback(db,sender,row.id,collaboration.FeedbackWrite(item_key=key,content='已补充'))
    collaboration.add_feedback(db,viewer,row.id,collaboration.FeedbackWrite(item_key=key,content='收到，谢谢'))
    rows=collaboration.feedback_rows(db,sender,row.id)['items']
    assert [r['content'] for r in rows]==['请补充客户需求','已补充','收到，谢谢']
    assert rows[0]['created_at'].utcoffset().total_seconds()==28800
    # Lulu 无报告查看规则也能监督全部沟通；不因此获得整份报告查看权。
    viewer.username='lulu';db.query(access.WorkReportAccessRule).delete();db.commit()
    assert len(collaboration.feedback_rows(db,viewer,row.id)['items'])==3
    assert collaboration.feedback_inbox(db,viewer)['total']==1
    with pytest.raises(HTTPException):access.received_report(db,viewer,row.id)
    assert len(collaboration.feedback_rows(db,owner,row.id)['items'])==3
    viewer.username='outsider';db.commit()
    with pytest.raises(HTTPException):collaboration.feedback_rows(db,viewer,row.id)
    # 工作行被移除后原工作项快照保留，作者仍可多次回复。
    row.items.clear();db.commit()
    collaboration.add_feedback(db,sender,row.id,collaboration.FeedbackWrite(item_key=key,content='原工作项的后续说明'))
    assert len(collaboration.feedback_rows(db,sender,row.id)['items'])==4


def test_statistics_only_admin_department_or_zhao_confirmed_only(environment,monkeypatch):
    db,(owner,viewer,sender)=environment
    from department_models import Department,DepartmentMember
    configure_user(db,owner)
    department=Department(id=uuid4(),name='行政部',aliases=[],revision=1);db.add(department)
    db.add(DepartmentMember(department_id=department.id,user_id=viewer.id,position='成员'))
    for person in [owner,viewer,sender]:person.created_at=datetime(2026,10,9)
    db.commit()
    monkeypatch.setattr(access,'now',lambda:datetime(2026,10,24,18,tzinfo=BUSINESS_TIMEZONE))
    report(db,sender,date(2026,10,10))
    report(db,viewer,date(2026,10,10),'draft')
    result=access.report_statistics(db,viewer,date(2026,10,10),'day')
    assert result['days'][0]['written_ids']==[str(sender.id)]
    assert set(result['days'][0]['missing_ids'])=={str(owner.id),str(viewer.id)}
    result=access.report_statistics(db,owner,date(2026,10,24),'month')
    assert all(day['date']<=date(2026,10,24) for day in result['days'])
    assert date(2026,10,1) not in [day['date'] for day in result['days']]
    person=next(p for p in result['people'] if p['id']==str(sender.id))
    assert date(2026,10,10) not in person['missing_dates']
    assert date(2026,10,9) in person['missing_dates']
    with pytest.raises(HTTPException):access.report_statistics(db,sender,date(2026,10,24),'week')


def test_one_amendment_after_sent_keeps_snapshot_and_feedback(environment,monkeypatch):
    db,(owner,viewer,sender)=environment
    import task_service as service
    from task_models import DailyReportItem
    from task_schemas import DailyReportItemInput,DailyReportSaveRequest
    from daily_report_mail_models import DailyReportMailDelivery
    rule(db,owner,viewer,sender)
    row=report(db,sender,date(2026,10,23));key=collaboration.item_key(row.items[0])
    collaboration.add_feedback(db,viewer,row.id,collaboration.FeedbackWrite(item_key=key,content='请修改任务说明'))
    sent=DailyReportMailDelivery(id=uuid4(),report_id=row.id,user_id=sender.id,sender_name_snapshot='测试',sender_email_snapshot='test@example.com',subject='原始发送',body_rows=[],body_html='',body_text='',status='sent',idempotency_key='sent-test-unique',smtp_message_id='test')
    db.add(sent);db.commit()
    monkeypatch.setattr(service,'derive_daily_report_items',lambda *args:[])
    original=DailyReportItem
    monkeypatch.setattr(service,'DailyReportItem',lambda **kwargs:original(id=uuid4(),**kwargs))
    payload=DailyReportSaveRequest(items=[DailyReportItemInput(source_type='manual',task_type='非项目工作',task_name='',progress_content='已补充说明',duration_minutes=10,display_metadata={'report_types':['非项目工作::接待客户'],'quantity':1,'quantity_unit':'次','_feedback_key':key})])
    updated=service.save_daily_report(db,sender,row.report_date,payload,finalize=True,amend=True)
    assert updated.status=='finalized'
    assert collaboration.item_key(updated.items[0])==key
    assert db.get(DailyReportMailDelivery,sent.id).status=='sent'
    history=collaboration.revision_history(db,viewer,row.id)
    assert history[0]['before']['items'][0]['progress_content']=='隔离工作报告'
    assert history[0]['after']['items'][0]['progress_content']=='已补充说明'
    assert len(collaboration.feedback_rows(db,sender,row.id)['items'])==1
    assert service.serialize_report(updated)['amendment_used']
    with pytest.raises(ValueError,match='一次修改机会已使用'):service.save_daily_report(db,sender,row.report_date,payload,finalize=True,amend=True)
    with pytest.raises(ValueError):service.withdraw_daily_report(db,sender,row.report_date)


def test_review_migration_and_authorized_default_rule_are_repeatable(environment,monkeypatch):
    db,(owner,viewer,sender)=environment
    from tools.apply_work_report_review_migration import apply_migration,seed_default_rule
    configure_user(db,owner)
    monkeypatch.setattr(access,'SUGGESTED_VIEWERS',[owner.username,viewer.username,sender.username])
    apply_migration(db.connection());apply_migration(db.connection())
    identifier=seed_default_rule(db)
    assert seed_default_rule(db)==identifier
    assert db.query(access.WorkReportAccessRule).count()==1
    assert access.sender_ids_for_rules(db,access.receiving_rules(db,viewer))=={owner.id,viewer.id,sender.id}


def test_note_only_amendment_retains_items_and_feedback_identity(environment,monkeypatch):
    db,(_,_,sender)=environment
    import task_service as service
    from task_models import DailyReportItem
    from task_schemas import DailyReportSaveRequest
    row=report(db,sender,date(2026,10,22));key=collaboration.item_key(row.items[0])
    original=DailyReportItem
    monkeypatch.setattr(service,'DailyReportItem',lambda **kwargs:original(id=uuid4(),**kwargs))
    monkeypatch.setattr(service,'derive_daily_report_items',lambda *args:pytest.fail('修订不应重新汇总'))
    saved=service.save_daily_report(db,sender,row.report_date,DailyReportSaveRequest(supplemental_note='仅补充说明'),finalize=True,amend=True)
    assert len(saved.items)==1 and collaboration.item_key(saved.items[0])==key
    assert saved.supplemental_note=='仅补充说明'
