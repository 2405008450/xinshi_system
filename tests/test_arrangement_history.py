from uuid import UUID
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from test_project_arrangement import create,completion
import project_arrangement as service
import project_arrangement_history as history


def test_history_create_edit_reorder_and_completion(environment):
    db,(owner,member,outsider)=environment
    project,first=create(db,owner,member)
    assert project.project_status=='arranged'
    second=service.create_assignments(db,owner,project.id,service.AssignmentBatch(items=[{'assignee_id':outsider.id,'content':'第二步任务','work_date':'2026-10-25'}]))[0]
    detail=history.detail(db,project.id)
    assert detail['revision']==2 and detail['history_total']==2
    first_history=detail['history'][-1]
    assert first_history['before_snapshot']['tasks']==[]
    service.edit_task(db,owner,first['id'],service.TaskEdit(revision=1,content='修改后的任务'),True)
    ordered=history.reorder(db,owner,project.id,history.ReorderWrite(revision=3,task_ids=[second['id'],first['id']]))
    assert [row['id'] for row in ordered['tasks']]==[second['id'],first['id']]
    mine=service.serialize(db,db.get(service.ProjectArrangement,first['id']))
    assert mine['execution_step']==2 and mine['execution_sequence'][0]['assignee_name']==outsider.full_name
    assert ordered['history'][0]['operation']=='reorder'
    edit=next(row for row in ordered['history'] if row['operation']=='edit')
    assert edit['before_snapshot']['tasks'][0]['content']=='核对稿件'
    assert edit['after_snapshot']['tasks'][0]['content']=='修改后的任务'
    service.complete_task(db,member,first['id'],completion(revision=2))
    assert history.detail(db,project.id)['history'][0]['operation']=='complete'
    assert first_history['after_snapshot']['tasks'][0]['content']=='核对稿件'


def test_order_rejects_stale_duplicate_missing_and_foreign_tasks(environment):
    db,(owner,member,outsider)=environment
    project,first=create(db,owner,member)
    for ids,revision in [([first['id']],0),([first['id'],first['id']],1),([owner.id],1)]:
        with pytest.raises(HTTPException) as failed:history.reorder(db,owner,project.id,history.ReorderWrite(revision=revision,task_ids=ids))
        assert failed.value.status_code==409
    assert history.detail(db,project.id)['revision']==1


def test_baseline_for_existing_tasks_and_repeatable_migration(environment):
    from tools.apply_arrangement_history_migration import apply_migration
    db,(owner,member,_)=environment
    project,first=create(db,owner,member)
    db.query(history.ArrangementHistory).delete();db.query(history.ArrangementPlan).delete();db.commit()
    assert history.detail(db,project.id)['history_total']==0
    service.edit_task(db,member,first['id'],service.TaskEdit(revision=1,estimated_minutes=30))
    events=history.detail(db,project.id)['history']
    assert [event['operation'] for event in events]==['edit','baseline']
    apply_migration(db.connection());apply_migration(db.connection())
