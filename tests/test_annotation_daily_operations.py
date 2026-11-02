"""今日操作状态与报告映射：仅使用内存 SQLite。"""
from datetime import timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from test_chat_participant_access import environment
from test_annotation_today_tasks import project
import annotation_daily_operations as service
from task_models import DailyReport, DailyReportItem
from chat_time import now
from work_report_dates import report_business_date


def create(db, user, projects, stage='in_progress'):
    return service.create(db, user, service.BatchWrite(work_date=report_business_date(now()),stage=stage, projects=[
        {'project_id': row.id, 'operations': [{'content': text, 'estimated_minutes': 30} for text in ['检查样本', '核对交付']]}
        for row in projects]))['items']


def edit(row, **values):
    return service.OperationEdit(**({'revision': row['revision'], 'stage': row['stage'],
        'content': row['content'], 'estimated_minutes': row['estimated_minutes'],
        'actual_minutes': row['actual_minutes'], 'quantity': row['quantity'] or None,
        'unit': row['unit']} | values))


def test_multi_project_operations_and_isolation(environment):
    from routers.project_arrangements import tasks
    db, (owner, member, outsider) = environment
    projects = [project(db, owner, member) for _ in range(2)]
    rows = create(db, member, projects, 'pending')
    assert len(rows) == 4 and len({row['id'] for row in rows}) == 4
    assert all(row['stage'] == 'pending' and not row['report_added'] for row in rows)
    assert len(service.context(db, member)['items']) == 4
    started = service.edit(db, member, rows[0]['id'], edit(rows[0], stage='in_progress'))
    assert started['stage'] == 'in_progress' and started['actual_minutes'] == 0
    assert not service.context(db, outsider)['items']
    with pytest.raises(HTTPException):
        service.edit(db, outsider, rows[0]['id'], edit(rows[0]))
    db.rollback()
    # 标注操作不混入笔译项目任务列表。
    day = report_business_date(now())
    assert tasks(day,False,None,None,[],1,10,db,member)['total'] == 0


def test_move_copy_edit_and_add_report_idempotently(environment):
    db, (owner, member, _) = environment
    row = create(db, member, [project(db, owner, member)])[0]
    performed = service.edit(db, member, row['id'], edit(row, stage='performed'))
    assert performed['actual_minutes'] == 30 and performed['stage'] == 'performed'
    with pytest.raises(HTTPException) as missing:
        service.add_report(db, member, row['id'], service.RevisionWrite(revision=performed['revision']))
    assert missing.value.status_code == 422
    db.rollback()
    updated = service.edit(db, member, row['id'], edit(performed, actual_minutes=20, quantity='2.5', unit='人'))
    result = service.add_report(db, member, row['id'], service.RevisionWrite(revision=updated['revision']))
    again = service.add_report(db, member, row['id'], service.RevisionWrite(revision=updated['revision']))
    assert result['report_added'] and again['report_added']
    entries = db.query(DailyReportItem).all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.display_metadata['report_types'] == ['标注项目']
    assert entry.display_metadata['order_no'] == row['order_no']
    assert entry.task_name == row['project_name'] and entry.progress_content == row['content']
    assert entry.duration_minutes == 20 and entry.display_metadata['quantity'] == '2.5'
    assert entry.display_metadata['quantity_unit'] == '人'
    with pytest.raises(HTTPException):
        service.edit(db, member, row['id'], edit(result, content='覆盖已加入报告的操作'))


def test_stale_revision_finalized_report_and_day_boundary(environment, monkeypatch):
    db, (owner, member, _) = environment
    row = create(db, member, [project(db, owner, member)])[0]
    updated = service.edit(db, member, row['id'], edit(row, stage='performed', quantity=1, unit='份'))
    with pytest.raises(HTTPException) as stale:
        service.edit(db, member, row['id'], edit(row))
    assert stale.value.status_code == 409
    db.rollback()
    from uuid import uuid4
    report = DailyReport(id=uuid4(),user_id=member.id,report_date=report_business_date(now()),status='finalized')
    db.add(report);db.commit()
    with pytest.raises(HTTPException) as finalized:
        service.add_report(db, member, row['id'], service.RevisionWrite(revision=updated['revision']))
    assert finalized.value.status_code == 409
    db.rollback()
    assert not service.context(db, member)['items'][0]['report_added']
    stamp = now() + timedelta(days=1)
    monkeypatch.setattr(service,'now',lambda:stamp)
    assert not service.context(db, member)['items']
    with pytest.raises(HTTPException) as changed_day:
        service.edit(db, member, row['id'], edit(updated))
    assert changed_day.value.status_code == 409
    db.rollback()
    with pytest.raises(HTTPException) as stale_create:
        service.create(db, member, service.BatchWrite(work_date=report_business_date(stamp)-timedelta(days=1),
            stage='pending',projects=[{'project_id': row['project_id'],
            'operations':[{'content':'旧窗口新增','estimated_minutes':30}]}]))
    assert stale_create.value.status_code == 409


def test_batch_rejects_unauthorized_project_before_saving(environment):
    db, (owner, member, outsider) = environment
    allowed, forbidden = project(db, owner, member), project(db, owner, outsider)
    with pytest.raises(HTTPException):
        create(db, member, [allowed, forbidden])
    db.rollback()
    assert not service.context(db, member)['items']
    with pytest.raises(ValidationError):
        service.OperationWrite(content=' ', estimated_minutes=30)
    with pytest.raises(ValidationError):
        service.OperationEdit(revision=1,stage='performed',content='检查',estimated_minutes=30,quantity=-1)


def test_picker_follows_current_arrangement_status_not_earlier_activity(environment):
    db, (owner, member, _) = environment
    row = project(db, owner, member)
    saved = service.status.save_arrangement(db, member, row.id,
        service.status.ArrangementWrite(revision=0,arrangement_status='in_progress',remaining_time='1_2h'))
    assert str(row.id) in {item['id'] for item in service.context(db, member)['projects']}
    paused = service.status.save_arrangement(db, member, row.id,
        service.status.ArrangementWrite(revision=saved['revision'],arrangement_status='not_today',remaining_time='1_2h'))
    # 今日曾进行不代表当前仍进行：选择器只看“是否今日进行”的当前值。
    assert not service.context(db, member)['projects']

    with pytest.raises(HTTPException) as rejected:
        create(db, member, [row])
    assert rejected.value.status_code == 403
    db.rollback()
    service.status.save_arrangement(db, member, row.id,
        service.status.ArrangementWrite(revision=paused['revision'],arrangement_status='in_progress',remaining_time='1_2h'))
    assert len(service.context(db, member)['projects']) == 1
    row.project_status = 'ended'
    db.commit()
    assert not service.context(db, member)['projects']


def test_import_own_translation_without_date_filter_is_repeatable(environment):
    from test_project_arrangement import create as assign
    from datetime import date
    db,(owner,member,outsider)=environment
    project,row=assign(db,owner,member)
    future=service.arrangements.ProjectArrangement(project_id=project.id,assignee_id=member.id,
        assigned_by=owner.id,content='未来安排也属于本人',work_date=date(2099,1,1))
    foreign=service.arrangements.ProjectArrangement(project_id=project.id,assignee_id=outsider.id,
        assigned_by=owner.id,content='他人任务',work_date=date(2020,1,1))
    db.add_all([future,foreign]);db.commit()
    service.personal.create(db,member,service.personal.TaskWrite(work_date=date(2020,1,1),item={
        'task_type':'项目工作','task_name':'','progress_content':'自己填写的笔译任务','duration_minutes':30,
        'display_metadata':{'report_types':['非项目工作','笔译项目'],'project_id':str(project.id)}}))
    payload=service.ImportWrite(work_date=report_business_date(now()),stage='pending')
    result=service.import_translation(db,member,payload)
    assert result['added']==3 and result['matched']==3
    assert {row['content'] for row in result['items']}=={'核对稿件','未来安排也属于本人','自己填写的笔译任务'}
    assert all(row['stage']=='pending' and row['project_type']=='笔译项目' for row in result['items'])
    again=service.import_translation(db,member,payload.model_copy(update={'stage':'in_progress'}))
    assert again['added']==0 and len(again['items'])==3
    assert all(row['stage']=='pending' for row in again['items'])


@pytest.mark.parametrize('kind',['assigned','personal'])
def test_translation_completion_updates_original_and_adds_one_report(environment,kind):
    from test_project_arrangement import create as assign
    db,(owner,member,_)=environment
    project,assignment=assign(db,owner,member)
    original_id=assignment['id']
    if kind=='personal':
        # 已完成安排不参与直接加入，只测试自主笔译来源。
        db.get(service.arrangements.ProjectArrangement,original_id).status='completed';db.commit()
        original=service.personal.create(db,member,service.personal.TaskWrite(work_date=report_business_date(now()),item={
            'task_type':'项目工作','progress_content':'自主笔译','duration_minutes':30,
            'display_metadata':{'report_types':['笔译项目'],'project_id':str(project.id)}}))
        original_id=original['id']
    imported=service.import_translation(db,member,service.ImportWrite(work_date=report_business_date(now()),stage='in_progress'))['items'][0]
    assert imported['content'] in ('核对稿件','自主笔译')
    performed=service.edit(db,member,imported['id'],edit(imported,stage='performed'))
    filled=service.edit(db,member,imported['id'],edit(performed,actual_minutes=20,quantity=3,unit='页'))
    result=service.add_report(db,member,imported['id'],service.RevisionWrite(revision=filled['revision']))
    source=service.linked_task(db,member.id,db.get(service.personal.PersonalDailyTask,imported['id']).report_row['display_metadata'])
    assert source.status=='completed' and source.report_item_id
    assert result['report_added'] and db.query(DailyReportItem).count()==1
    entry=db.query(DailyReportItem).one()
    assert entry.display_metadata['report_types']==['笔译项目'] and entry.display_metadata['order_no']==project.order_no
    assert entry.duration_minutes==20
    service.add_report(db,member,imported['id'],service.RevisionWrite(revision=filled['revision']))
    assert db.query(DailyReportItem).count()==1


@pytest.mark.parametrize('project_type',['口译项目','招聘项目','非项目任务'])
def test_other_task_entries_create_and_report_with_correct_type(environment,project_type):
    from uuid import uuid4
    db,(owner,member,_)=environment
    project_id=None
    if project_type!='非项目任务':
        model=service.picker.PROJECT_MODELS[project_type]
        project=model(id=uuid4(),order_no='OTHER-TEST',project_name='其他项目',created_by=owner.id)
        db.add(project);db.commit();project_id=project.id
        if project_type=='口译项目':
            from project_client_manager import ProjectClientManagerChange
            member.department='口译项目部'
            db.add(ProjectClientManagerChange(id=uuid4(),project_type='interpretation',project_id=project.id,
                revision=1,new_manager_id=member.id,reason='测试'))
            db.commit()
    row=service.create(db,member,service.BatchWrite(work_date=report_business_date(now()),project_type=project_type,
        stage='pending',projects=[{'project_id':project_id,'operations':[{'content':'具体工作','estimated_minutes':30}]}]))['items'][0]
    expected='非项目工作' if project_type=='非项目任务' else project_type
    assert row['project_type']==expected
    performed=service.edit(db,member,row['id'],edit(row,stage='performed'))
    filled=service.edit(db,member,row['id'],edit(performed,actual_minutes=20,quantity=1,unit='次'))
    service.add_report(db,member,row['id'],service.RevisionWrite(revision=filled['revision']))
    entry=db.query(DailyReportItem).one()
    assert entry.display_metadata['report_types']==[expected]


def test_original_translation_completed_elsewhere_does_not_duplicate_report(environment):
    from test_project_arrangement import create as assign,completion
    db,(owner,member,_)=environment
    _,assignment=assign(db,owner,member)
    imported=service.import_translation(db,member,service.ImportWrite(work_date=report_business_date(now()),stage='in_progress'))['items'][0]
    performed=service.edit(db,member,imported['id'],edit(imported,stage='performed'))
    service.arrangements.complete_task(db,member,assignment['id'],completion())
    assert service.context(db,member)['items'][0]['report_added']
    service.add_report(db,member,imported['id'],service.RevisionWrite(revision=performed['revision']))
    assert db.query(DailyReportItem).count()==1


def test_imported_translation_suborder_keeps_identity_in_report(environment):
    from test_arrangement_order_targets import orders,batch
    db,(owner,member,_)=environment
    root,child,_,_=orders(db,owner)
    service.arrangements.create_assignments(db,owner,root.id,batch(member,[child.id]))
    row=service.import_translation(db,member,service.ImportWrite(work_date=report_business_date(now()),stage='in_progress'))['items'][0]
    assert row['order_no']==child.sub_order_no and row['project_name']==child.sub_project_name
    performed=service.edit(db,member,row['id'],edit(row,stage='performed'))
    filled=service.edit(db,member,row['id'],edit(performed,actual_minutes=20,quantity=1,unit='份'))
    service.add_report(db,member,row['id'],service.RevisionWrite(revision=filled['revision']))
    entry=db.query(DailyReportItem).one()
    assert entry.task_name==child.sub_project_name
    assert entry.display_metadata['order_no']==child.sub_order_no
    assert entry.display_metadata['sub_order_id']==str(child.id)
