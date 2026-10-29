from datetime import date
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_chat_participant_access import environment
import personal_daily_task as personal
from project_arrangement import TaskEdit,TaskComplete
from routers.project_arrangements import tasks


def task_write(day='2026-10-25',**metadata):
    return personal.TaskWrite(work_date=day,item={'task_type':'非项目工作','task_name':'','progress_content':'自行研究系统交互','duration_minutes':30,'display_metadata':{'report_types':['非项目工作::研究工作'],**metadata}})


def test_multiple_task_rows_atomic_validation_and_independent_tasks(environment):
    from uuid import uuid4
    db,(owner,_,_)=environment
    item=task_write().item
    invalid=item.model_copy(deep=True)
    invalid.display_metadata={'report_types':['笔译项目'],'project_id':str(uuid4())}
    with pytest.raises(HTTPException):
        personal.create_many(db,owner,personal.TasksWrite(work_date='2026-10-25',items=[item,invalid]))
    assert db.query(personal.PersonalDailyTask).count()==0
    child=item.model_copy(deep=True)
    child.display_metadata['parent_item_key']=str(uuid4())
    result=personal.create_many(db,owner,personal.TasksWrite(work_date='2026-10-25',items=[item,child]))
    assert len(result['items'])==2
    assert len({row['id'] for row in result['items']})==2
    assert all('parent_item_key' not in row['report_row']['display_metadata'] for row in result['items'])
    assert all(row['status']=='pending' for row in result['items'])
    with pytest.raises(ValidationError):personal.TasksWrite(work_date='2026-10-25',items=[])
    with pytest.raises(ValidationError):personal.TasksWrite(work_date='2026-10-25',items=[item]*101)


def test_can_add_multiple_personal_rows_when_already_assigned(environment):
    from test_project_arrangement import create
    db,(owner,member,_)=environment
    create(db,owner,member)
    personal.create_many(db,member,personal.TasksWrite(work_date='2026-10-25',items=[task_write().item]*3))
    listing=tasks(date(2026,10,25),False,None,None,[],1,10,db,member)
    assert listing['total']==4
    assert {row['source'] for row in listing['items']}=={'assigned','personal'}


def test_personal_task_without_assignment_and_date_archive(environment):
    db,(owner,other,_)=environment
    saved=personal.create(db,owner,task_write())
    personal.create(db,owner,task_write('2026-10-20'))
    personal.create(db,other,task_write())
    listing=tasks(date(2026,10,25),False,None,None,[],1,10,db,owner)
    assert listing['total']==2 and all(row['source']=='personal' for row in listing['items'])
    exact=tasks(date(2026,10,25),False,None,None,[],1,10,db,owner,date(2026,10,25),date(2026,10,25))
    assert exact['total']==1 and exact['items'][0]['id']==saved['id']
    old=tasks(date(2026,10,25),False,None,None,[],1,10,db,owner,date(2026,10,19),date(2026,10,21))
    assert old['total']==1
    with pytest.raises(HTTPException):personal.edit(db,other,saved['id'],TaskEdit(revision=1,status='in_progress'))
    db.rollback()
    updated=personal.edit(db,owner,saved['id'],TaskEdit(revision=1,actual_minutes=20))
    assert updated['actual_minutes']==20


def test_personal_complete_requires_full_report_and_preserves_report(environment,monkeypatch):
    from task_models import DailyReport,DailyReportItem
    import task_service
    from task_schemas import DailyReportSaveRequest
    from work_report_dates import report_business_date
    from chat_time import now
    from sqlalchemy import event
    from uuid import uuid4
    db,(owner,_,_)=environment
    saved=personal.create(db,owner,task_write())
    data={'source_type':'manual','task_type':'非项目工作','task_name':'','progress_content':'研究已完成','duration_minutes':30,'display_metadata':{'report_types':['非项目工作::研究工作'],'quantity':'1','quantity_unit':'份'}}
    invalid={**data,'duration_minutes':0}
    with pytest.raises(ValidationError):TaskComplete(revision=1,item=invalid)
    forged={**invalid,'source_type':'system_event','display_metadata':{'report_types':['非项目工作::研究工作']}}
    with pytest.raises(HTTPException) as rejected:personal.complete(db,owner,saved['id'],TaskComplete(revision=1,item=forged))
    assert rejected.value.status_code==422
    assert db.get(personal.PersonalDailyTask,saved['id']).status=='pending'
    result=personal.complete(db,owner,saved['id'],TaskComplete(revision=1,item=data))
    assert result['status']=='completed'
    assert db.query(DailyReportItem).one().display_metadata['personal_task_id']==str(saved['id'])
    def assign_id(mapper,connection,target):
        if target.id is None:target.id=uuid4()
    event.listen(DailyReportItem,'before_insert',assign_id)
    monkeypatch.setattr(task_service,'derive_daily_report_items',lambda *args:[])
    try:report=task_service.save_daily_report(db,owner,report_business_date(now()),DailyReportSaveRequest(items=[]))
    finally:event.remove(DailyReportItem,'before_insert',assign_id)
    assert len(report.items)==1


def test_project_picker_identity_is_canonical_and_search_is_literal(environment):
    from models import TranslationProject
    from uuid import uuid4
    import report_project_picker as picker
    db,(owner,_,_)=environment
    project=TranslationProject(id=uuid4(),order_no='TP-TEST-AA',project_name='BB AA % literal',source_file_name='BB AA % literal')
    db.add(project);db.commit()
    assert picker.search(db,'笔译项目','AA BB',1,10)['total']==1
    assert picker.search(db,'笔译项目','%',1,10)['total']==1
    payload=personal.TaskWrite(work_date='2026-10-25',item={'task_type':'项目工作','task_name':'伪造名称','progress_content':'处理测试项目','display_metadata':{'report_types':['笔译项目'],'project_id':str(project.id),'order_no':'伪造订单'}})
    row=personal.create(db,owner,payload)
    assert row['order_no']==project.order_no and row['project_name']==project.project_name
    with pytest.raises(HTTPException):picker.resolve(db,'口译项目',project.id)


def test_review_scope_applies_to_self_filled_tasks(environment):
    import work_report_access as access
    db,(owner,member,outsider)=environment
    owner.username='williamzhao';db.commit()
    personal.create(db,member,task_write());personal.create(db,outsider,task_write())
    access.save_rule(db,owner,access.AccessRuleWrite(name='自主任务范围',viewer_ids=[owner.id],sender_ids=[member.id]))
    result=tasks(date(2026,10,25),True,None,None,[],1,10,db,owner)
    assert result['total']==1 and result['items'][0]['assignee_id']==member.id


def test_personal_table_migration_is_repeatable(environment):
    from tools.apply_personal_daily_task_migration import apply_migration
    db,_=environment
    personal.PersonalDailyTask.__table__.drop(db.connection(),checkfirst=True)
    apply_migration(db.connection());apply_migration(db.connection())
    assert personal.ready(db)
