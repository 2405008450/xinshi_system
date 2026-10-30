from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_technical_development import environment, setup, payload
import technical_development as tasks
import technical_task_management as management
from routers.technical_development import SwapWrite


def tree(db,owner,executor):
    a=tasks.create_task(db,owner,payload(owner,executor,'A'))
    b=tasks.create_task(db,owner,payload(owner,executor,'B',parent_id=a['id']))
    c=tasks.create_task(db,owner,payload(owner,executor,'C',parent_id=b['id']))
    return a,b,c


def test_hierarchy_numbers_and_no_reuse_after_delete(setup):
    db,(owner,executor,_)=setup
    a,b,c=tree(db,owner,executor)
    assert b['task_no']==a['task_no']+'.001'
    assert c['task_no']==b['task_no']+'.001'
    second=tasks.create_task(db,owner,payload(owner,executor,'D',parent_id=a['id']))
    assert second['task_no']==a['task_no']+'.002'
    management.delete_task(db,owner,second['id'],second['revision'])
    third=tasks.create_task(db,owner,payload(owner,executor,'E',parent_id=a['id']))
    assert third['task_no']==a['task_no']+'.003'


def test_reparent_renumbers_whole_subtree_preserving_records(setup):
    db,(owner,executor,_)=setup
    a,b,c=tree(db,owner,executor)
    d=tasks.create_task(db,owner,payload(owner,executor,'D'))
    moved=tasks.update_task(db,owner,b['id'],tasks.TaskMove(parent_id=d['id'],revision=b['revision']))
    assert moved['task_no']==d['task_no']+'.001'
    assert tasks.detail(db,owner,c['id'])['task_no']==moved['task_no']+'.001'
    assert moved['name']=='B' and moved['id']==b['id']
    root=tasks.update_task(db,owner,b['id'],tasks.TaskMove(parent_id=None,revision=moved['revision']))
    assert '.' not in root['task_no']
    assert tasks.detail(db,owner,c['id'])['task_no']==root['task_no']+'.001'
    new=tasks.create_task(db,owner,payload(owner,executor,'New root'))
    assert new['task_no'] != root['task_no']


@pytest.mark.parametrize('target_index',[1,2])
def test_swap_ancestor_child_or_third_level(setup,target_index):
    db,(owner,executor,_)=setup
    rows=tree(db,owner,executor)
    a=rows[0];other=rows[target_index]
    tasks.update_task(db,owner,a['id'],tasks.ProgressWrite(percentage=75,content='A进度',revision=a['revision']))
    management.swap_tasks(db,owner,a['id'],SwapWrite(target_id=other['id'],revision=2,target_revision=1))
    updated_a=tasks.detail(db,owner,a['id']);updated_other=tasks.detail(db,owner,other['id'])
    assert updated_a['task_no']==other['task_no'] and updated_other['task_no']==a['task_no']
    assert updated_other['parent_id'] is None
    assert updated_a['name']=='A' and updated_a['progress']==75 and updated_a['progress_history'][0]['content']=='A进度'
    for row in tasks.list_tasks(db,owner)['items']:
        if row['parent_id']:
            parent=tasks.detail(db,owner,row['parent_id'])
            assert row['task_no'].rsplit('.',1)[0]==parent['task_no']


def test_delete_preserves_reports_history_and_blocks_mutation(setup):
    from task_models import DailyReport
    from test_technical_development_report import request
    import technical_development_report as reports
    db,(owner,executor,_)=setup
    a,b,c=tree(db,owner,executor)
    with pytest.raises(HTTPException) as error: management.delete_task(db,owner,a['id'],a['revision'])
    assert error.value.status_code==409
    result=reports.submit(db,owner,c['id'],request())
    tasks.add_feedback(db,owner,c['id'],tasks.FeedbackWrite(content='保留反馈'))
    management.delete_task(db,owner,c['id'],1)
    assert len(db.get(DailyReport,result['report_id']).items)==1
    assert tasks.detail(db,owner,c['id'])['deleted'] is True
    assert tasks.detail(db,owner,c['id'])['feedback'][0]['content']=='保留反馈'
    assert c['id'] not in {row['id'] for row in tasks.list_tasks(db,owner)['items']}
    with pytest.raises(HTTPException) as error: tasks.update_task(db,owner,c['id'],tasks.ProgressWrite(percentage=50,revision=2))
    assert error.value.status_code==410
    management.delete_task(db,owner,b['id'],b['revision'])
    management.delete_task(db,owner,a['id'],a['revision'])


def test_permissions_versions_and_migration_idempotency(setup):
    from tools.apply_technical_task_management_migration import apply_migration
    db,(owner,executor,outsider)=setup
    a,b,c=tree(db,owner,executor)
    with pytest.raises(HTTPException) as error: management.delete_task(db,outsider,c['id'],1)
    assert error.value.status_code==403
    with pytest.raises(HTTPException) as error: management.delete_task(db,owner,c['id'],99)
    assert error.value.status_code==409
    with pytest.raises(HTTPException): management.swap_tasks(db,owner,a['id'],SwapWrite(target_id=c['id'],revision=99,target_revision=1))
    before=management.numbers(db)
    for table in reversed(management.TABLES): table.drop(db.connection())
    db.commit()
    with db.bind.begin() as connection: apply_migration(connection)
    with db.bind.begin() as connection: apply_migration(connection)
    db.expire_all()
    assert management.numbers(db)==before
    assert db.query(management.TaskHierarchyNumber).count()==3


def test_deleted_collaboration_is_hidden_and_blocks_each_execution(setup):
    db,(owner,executor,_)=setup
    task=tasks.create_task(db,owner,payload(owner,executor,allocations=[tasks.ExecutorAllocation(executor_id=executor.id,content='页面'),tasks.ExecutorAllocation(executor_id=owner.id,content='接口')]))
    execution_ids={item['task_id'] for item in task['allocations']}
    management.delete_task(db,owner,task['id'],task['revision'])
    assert not tasks.list_tasks(db,owner)['items']
    assert execution_ids <= management.deleted_ids(db)
    for uid in execution_ids:
        with pytest.raises(HTTPException): tasks.get_task(db,uid)
        assert tasks.detail(db,owner,uid)['deleted'] is True


def test_http_delete_and_swap_permissions(setup):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.technical_development import router
    db,(owner,executor,outsider)=setup
    a,b,c=tree(db,owner,executor)
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:outsider
    client=TestClient(app)
    assert client.delete(f"/technical-development/tasks/{c['id']}?revision=1").status_code==403
    body=dict(target_id=str(c['id']),revision=1,target_revision=1)
    assert client.put(f"/technical-development/tasks/{a['id']}/swap",json=body).status_code==403
    app.dependency_overrides[get_current_user]=lambda:owner
    assert client.put(f"/technical-development/tasks/{a['id']}/swap",json=body).status_code==200
    assert client.delete(f"/technical-development/tasks/{a['id']}?revision=1").status_code==409
    assert client.delete(f"/technical-development/tasks/{a['id']}?revision=2").status_code==200
