from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_technical_development import environment,setup,payload
from test_technical_task_incentives import completed,amount,hr
import technical_development as tasks
import technical_task_allocations as service
import technical_task_incentives as incentives


def divisions(owner,executor):
    return [dict(executor_id=owner.id,content='接口开发',due_at='2026-10-30T18:00:00+08:00'),dict(executor_id=executor.id,content='页面开发',due_at='2026-11-01T18:00:00+08:00')]


def create(db,owner,executor,**extra):
    return tasks.create_task(db,owner,payload(owner,owner,allocations=divisions(owner,executor),**extra))


def test_multiple_executors_at_third_level_hidden_execution_records_and_independent_amounts(setup):
    db,(owner,executor,administrator)=setup
    first=tasks.create_task(db,owner,payload(owner,owner))
    second=tasks.create_task(db,owner,payload(owner,owner,parent_id=first['id']))
    row=create(db,owner,executor,parent_id=second['id'])
    assert row['has_allocations'] and len(row['allocations'])==2
    assert row['executor_ids']==[owner.id,executor.id]
    assert len(tasks.list_tasks(db,owner)['items'])==3
    assert db.query(tasks.DevelopmentTask).count()==5
    assert len({part['task_no'] for part in row['allocations']})==2
    a,b=row['allocations']
    amount(db,owner,completed(db,owner,dict(id=a['task_id']),'2026-10-31'),'30')
    amount(db,owner,completed(db,owner,dict(id=b['task_id']),'2026-10-31'),'80')
    refreshed=tasks.detail(db,owner,row['id'])
    assert refreshed['allocations'][0]['on_time'] is False and refreshed['allocations'][1]['on_time'] is True
    assert refreshed['on_time'] is None and refreshed['incentive'] is None
    stats=incentives.statistics(db,hr(db,administrator))
    assert stats['totals']['reward_total']=='80.00' and stats['totals']['deduction_total']=='30.00'
    assert stats['totals']['offset_total']=='0.00' and len(stats['people'])==2
    assert {item['task_id'] for item in stats['tasks']}=={a['task_id'],b['task_id']}


def test_allocation_edits_reuse_ids_and_reassess_only_changed_person(setup):
    db,(owner,executor,administrator)=setup
    row=create(db,owner,executor)
    a,b=row['allocations']
    amount(db,owner,completed(db,owner,dict(id=a['task_id']),'2026-10-30'),'50')
    amount(db,owner,completed(db,owner,dict(id=b['task_id']),'2026-10-31'),'80')
    values=divisions(owner,executor);values[1]['due_at']='2026-10-30T18:00:00+08:00'
    fields=payload(owner,owner,allocations=values).model_dump(exclude={'parent_id'})
    updated=tasks.update_task(db,owner,row['id'],tasks.TaskUpdate(**fields,revision=1))
    assert [part['task_id'] for part in updated['allocations']]==[a['task_id'],b['task_id']]
    assert updated['allocations'][0]['incentive']['amount']=='50.00'
    assert updated['allocations'][1]['incentive'] is None and updated['allocations'][1]['on_time'] is False
    assert incentives.statistics(db,hr(db,administrator))['totals']['reward_total']=='50.00'


def test_converting_completed_single_task_preserves_money_without_double_counting(setup):
    db,(owner,executor,administrator)=setup
    row=tasks.create_task(db,owner,payload(owner,owner,due_at='2026-10-30T18:00:00+08:00'))
    amount(db,owner,completed(db,owner,row,'2026-10-30'),'100')
    fields=payload(owner,owner,allocations=divisions(owner,executor)).model_dump(exclude={'parent_id'})
    updated=tasks.update_task(db,owner,row['id'],tasks.TaskUpdate(**fields,revision=1))
    assert updated['allocations'][0]['completed_on'].isoformat()=='2026-10-30'
    assert updated['allocations'][0]['incentive']['amount']=='100.00'
    stats=incentives.statistics(db,hr(db,administrator))
    assert stats['totals']['reward_total']=='100.00' and len(stats['tasks'])==1
    assert not any(item['effective'] for item in incentives.read(db,owner,row['id'])['ledger_history'])


def test_validation_and_coordinator_completion_report_guards(setup):
    db,(owner,executor,outsider)=setup
    with pytest.raises(ValidationError):payload(owner,owner,allocations=[divisions(owner,executor)[0]]*2)
    with pytest.raises(ValidationError):payload(owner,owner,allocations=[dict(executor_id=owner.id,content=' ')])
    with pytest.raises(HTTPException):create(db,owner,outsider)
    row=create(db,owner,executor)
    with pytest.raises(HTTPException):completed(db,owner,row,'2026-10-30')
    import technical_development_report as report
    with pytest.raises(HTTPException):report.context(db,owner,row['id'])
    assert report.context(db,owner,row['allocations'][0]['task_id'])['progress_content']=='接口开发'


def test_removed_completed_division_keeps_history_and_cannot_accept_new_amount(setup):
    db,(owner,executor,administrator)=setup
    row=create(db,owner,executor);a,b=row['allocations']
    result=amount(db,owner,completed(db,owner,dict(id=b['task_id']),'2026-10-31'),'80')
    fields=payload(owner,owner,allocations=[divisions(owner,executor)[0]]).model_dump(exclude={'parent_id'})
    updated=tasks.update_task(db,owner,row['id'],tasks.TaskUpdate(**fields,revision=1))
    assert len(updated['allocations'])==1
    with pytest.raises(HTTPException):amount(db,owner,result,'90','已移出分工')
    assert incentives.statistics(db,hr(db,administrator))['totals']['reward_total']=='80.00'


def test_migration_create_only_idempotent(setup):
    db,(owner,executor,_)=setup
    row=tasks.create_task(db,owner,payload(owner,executor))
    from tools.apply_technical_allocations_migration import apply_migration
    for table in reversed(service.TABLES):table.drop(db.connection())
    db.commit();apply_migration(db.connection());apply_migration(db.connection());db.commit()
    assert service.ready(db) and not tasks.detail(db,owner,row['id']).get('has_allocations')


def test_completed_original_executor_not_selected_keeps_earned_amount(setup):
    from models import AppUser
    db,(owner,executor,administrator)=setup
    third=AppUser(id=uuid4(),username='third-technical',full_name='第三人',password_hash='disabled',is_active=True,is_deleted=False,department='IT部')
    db.add(third);db.commit()
    row=tasks.create_task(db,owner,payload(owner,owner,due_at='2026-10-30T18:00:00+08:00'))
    amount(db,owner,completed(db,owner,row,'2026-10-30'),'100')
    fields=payload(owner,executor,allocations=divisions(executor,third)).model_dump(exclude={'parent_id'})
    updated=tasks.update_task(db,owner,row['id'],tasks.TaskUpdate(**fields,revision=1))
    assert updated['executor_ids']==[executor.id,third.id]
    legacy=db.query(service.TaskAllocation).filter_by(root_task_id=row['id'],executor_id=owner.id).one()
    assert not legacy.active
    stats=incentives.statistics(db,hr(db,administrator))
    assert stats['totals']['reward_total']=='100.00'
    assert len(tasks.list_tasks(db,owner)['items'])==1
