"""开拓问题回归，仅连接本机专用隔离库，逐例回滚。"""
import os
from datetime import timedelta
from uuid import uuid4
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy import text
from resource_issue_schemas import IssueCreate, IssueUpdate, IssueTaskWrite


@pytest.fixture
def environment():
    if os.getenv('RESOURCE_ISSUES_QA') != '1':
        pytest.skip('使用 tools/verify_resource_issues.py 启动隔离验收')
    import main
    from database import engine
    from tools.resource_issues_fixture import seed
    assert engine.url.host=='127.0.0.1' and engine.url.username=='issue_test' and engine.url.database=='issues_test'
    with engine.connect() as connection:
        transaction=connection.begin()
        with Session(bind=connection,join_transaction_mode='create_savepoint',expire_on_commit=False) as db:
            yield db, seed(db)
        transaction.rollback()


def create(db, data, category='problem', kind='annotation', actor=None, **changes):
    import resource_issue_service as service
    payload=IssueCreate(source_message_id=data['messages'][kind].id,category=category,content='整理后的问题内容',**changes)
    return service.create_issue(db,actor or data['users']['collector'],payload)


def task(db,data,row,actor=None,**values):
    import resource_issue_service as service
    return service.write_task(db,actor or data['users']['collector'],row['id'],IssueTaskWrite(revision=row['revision'],content='联系相关人员',executor_id=data['users']['executor'].id,**values))


def test_payload_rejects_spoofing_and_blank_content():
    common=dict(source_message_id=uuid4(),category='problem',content='问题')
    for fields in [dict(content='  '),dict(category='invalid'),dict(proposer_id=uuid4()),dict(source_title='伪造来源'),dict(created_at='2020-01-01')]:
        with pytest.raises(ValidationError):IssueCreate(**(common|fields))
    for fields in [dict(status=None),dict(executor_id=None),dict(progress=None),dict(content='  ')]:
        with pytest.raises(ValidationError):IssueTaskWrite(revision=1,**fields)


def test_summary_migration_removes_legacy_category_constraint(environment):
    """还原线上新旧约束并存状态，验证增量迁移及八类消息实际入库。"""
    db, data = environment
    from tools.apply_chat_summary_migration import apply_migration
    from sqlalchemy import inspect
    from sqlalchemy.exc import IntegrityError
    from resource_issue_models import DevelopmentIssue

    db.execute(text("ALTER TABLE resource_development_issue ADD CONSTRAINT resource_development_issue_category_check CHECK (category IN ('arrangement','execution','problem','idea'))"))
    with pytest.raises(IntegrityError) as blocked:
        with db.begin_nested():
            create(db, data, category='request', kind='direct')
    assert 'resource_development_issue_category_check' in str(blocked.value)
    # 新约束已存在时，旧脚本会跳过更新，从而遗漏自动命名的旧约束。
    apply_migration(db.connection())
    apply_migration(db.connection())
    names = {item['name'] for item in inspect(db.connection()).get_check_constraints('resource_development_issue')}
    assert 'resource_development_issue_category_check' not in names
    assert 'ck_development_issue_category' in names
    for category in ['arrangement', 'request', 'idea', 'decision', 'execution', 'problem', 'risk', 'standard']:
        row = create(db, data, category=category, kind='direct')
        assert row['category'] == category
    assert db.query(DevelopmentIssue).count() == 8
    with pytest.raises(IntegrityError) as invalid:
        with db.begin_nested():
            db.execute(text("UPDATE resource_development_issue SET category='invalid'"))
    assert 'ck_development_issue_category' in str(invalid.value)


@pytest.mark.parametrize('kind',['translation','annotation','direct'])
@pytest.mark.parametrize('category',['arrangement','execution','problem','idea'])
def test_three_sources_four_categories_and_idempotency(environment,kind,category):
    db,data=environment
    from resource_issue_models import DevelopmentIssue
    row=create(db,data,category,kind)
    assert row['source_type']==kind and row['category']==category and row['proposer_id']==str(data['users']['proposer'].id)
    assert row['source_content']==data['messages'][kind].content and row['content']=='整理后的问题内容'
    assert row['created_at'].endswith('+08:00') and row['updated_at'].endswith('+08:00')
    retry=create(db,data,category,kind)
    assert retry['id']==row['id'] and retry['already_collected']
    assert db.query(DevelopmentIssue).count()==1


def test_associated_access_and_private_source_no_admin_bypass(environment):
    db,data=environment
    import resource_issue_service as service
    from routers.resource_issues import locate_source
    row=create(db,data,kind='direct')
    assert service.capabilities(db,data['users']['proposer'])['can_enter']
    assert not service.capabilities(db,data['users']['proposer'])['can_resource']
    with pytest.raises(HTTPException):service.get_issue(db,data['users']['executor'],row['id'])
    row=task(db,data,row)
    assert service.capabilities(db,data['users']['executor'])['can_enter']
    assert not service.capabilities(db,data['users']['executor'])['can_resource']
    for key in ['collector','proposer','executor','manager','admin']:
        assert service.get_issue(db,data['users'][key],row['id'])
    for key in ['executor','manager','admin']:
        assert not locate_source(row['id'],db,data['users'][key])['available']
    assert locate_source(row['id'],db,data['users']['collector'])['available']
    with pytest.raises(HTTPException):service.get_issue(db,data['users']['outsider'],row['id'])
    with pytest.raises(HTTPException):create(db,data,kind='direct',actor=data['users']['admin'])


def test_executor_limits_completion_and_revision(environment):
    db,data=environment
    import resource_issue_service as service
    from resource_issue_models import business_now,DevelopmentIssueTask
    row=task(db,data,create(db,data))
    task_id=row['tasks'][0]['id'];executor=data['users']['executor']
    with pytest.raises(HTTPException) as forbidden:
        service.write_task(db,executor,row['id'],IssueTaskWrite(revision=row['revision'],content='试图改安排'),task_id)
    assert forbidden.value.status_code==403
    completed=service.write_task(db,executor,row['id'],IssueTaskWrite(revision=row['revision'],status='completed',progress='执行完成'),task_id)
    assert completed['tasks'][0]['completed_date']==business_now().date().isoformat()
    with pytest.raises(HTTPException) as conflict:
        service.write_task(db,executor,row['id'],IssueTaskWrite(revision=row['revision'],status='pending'),task_id)
    assert conflict.value.status_code==409
    history=business_now().date()-timedelta(days=4)
    updated=service.write_task(db,executor,row['id'],IssueTaskWrite(revision=completed['revision'],completed_date=history),task_id)
    assert updated['tasks'][0]['completed_date']==history.isoformat()
    reopened=service.write_task(db,executor,row['id'],IssueTaskWrite(revision=updated['revision'],status='in_progress'),task_id)
    assert reopened['tasks'][0]['completed_date'] is None
    # 失败请求在实际接口的独立事务中回滚；这里使用 savepoint 模拟。
    with pytest.raises(HTTPException) as future:
        with db.begin_nested():
            service.write_task(db,executor,row['id'],IssueTaskWrite(revision=reopened['revision'],status='completed',completed_date=business_now().date()+timedelta(days=1)),task_id)
    assert future.value.status_code==422
    assert db.get(DevelopmentIssueTask,task_id).status=='in_progress'


def test_reassignment_removes_former_executor_access_and_inactive_rejected(environment):
    db,data=environment
    import resource_issue_service as service
    row=task(db,data,create(db,data));task_id=row['tasks'][0]['id']
    row=service.write_task(db,data['users']['collector'],row['id'],IssueTaskWrite(revision=row['revision'],executor_id=data['users']['outsider'].id),task_id)
    with pytest.raises(HTTPException):service.get_issue(db,data['users']['executor'],row['id'])
    assert service.get_issue(db,data['users']['outsider'],row['id'])
    with pytest.raises(HTTPException):service.write_task(db,data['users']['collector'],row['id'],IssueTaskWrite(revision=row['revision'],executor_id=data['users']['inactive'].id),task_id)


def test_filters_use_same_task_and_keyword_total(environment):
    db,data=environment
    from routers.resource_issues import listing
    row=task(db,data,create(db,data),status='pending',planned_date='2026-10-12')
    import resource_issue_service as service
    row=service.write_task(db,data['users']['collector'],row['id'],IssueTaskWrite(revision=row['revision'],content='另一任务含%_字符',executor_id=data['users']['outsider'].id,status='completed'))
    def listed(**filters):
        return listing(**(dict(keyword=None,category=None,proposer_id=None,executor_id=None,status=None,planned_start=None,planned_end=None,skip=0,limit=20,db=db,actor=data['users']['collector'])|filters))
    assert listed(executor_id=data['users']['executor'].id,status='completed')['total']==0
    assert listed(executor_id=data['users']['executor'].id,status='pending',planned_start=__import__('datetime').date(2026,10,12))['total']==1
    assert listed(keyword='%_')['total']==1 and len(listed(keyword='%_',limit=1)['items'])==1
    assert listed(keyword='不会匹配')['total']==0


def test_recalled_deleted_and_system_sources_preserve_snapshot(environment):
    db,data=environment
    import resource_issue_service as service
    from resource_issue_models import business_now
    row=create(db,data)
    message=data['messages']['annotation'];message.recalled_at=business_now().replace(tzinfo=None);db.flush()
    with pytest.raises(HTTPException):create(db,data,category='idea')
    assert service.serialize(db,data['users']['collector'],service.get_issue(db,data['users']['collector'],row['id']),detail=True)['source_content']==row['source_content']
    db.delete(message);db.flush()
    assert service.get_issue(db,data['users']['collector'],row['id'])
    with pytest.raises(HTTPException):service.source_preview(db,data['users']['collector'],message.id)
    for kind in ('translation','direct'):
        data['messages'][kind].message_type='handover';db.flush()
        with pytest.raises(HTTPException):create(db,data,kind=kind)


def test_manager_edit_but_not_delete_other_collection_audit(environment):
    db,data=environment
    import resource_issue_service as service
    from resource_issue_models import DevelopmentIssue,DevelopmentIssueTask
    from resource_development_models import DevelopmentAudit
    row=task(db,data,create(db,data))
    row=service.update_issue(db,data['users']['manager'],row['id'],IssueUpdate(content='统筹修订',revision=row['revision']))
    with pytest.raises(HTTPException):service.delete_issue(db,data['users']['manager'],row['id'],row['revision'])
    service.delete_issue(db,data['users']['collector'],row['id'],row['revision']);db.flush()
    assert not db.query(DevelopmentIssue).count() and not db.query(DevelopmentIssueTask).count()
    deleted=db.query(DevelopmentAudit).filter(DevelopmentAudit.action=='delete').all()
    assert {r.entity_type for r in deleted}=={'issue','issue_task'}
    assert all(r.before for r in deleted)


def test_http_auth_extra_fields_associated_access_and_transactions(environment):
    db,data=environment
    from routers import resource_issues,auth
    from database import get_db
    app=FastAPI();app.include_router(resource_issues.router)
    actor=[data['users']['collector']]
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[auth.get_current_user]=lambda:actor[0]
    with TestClient(app) as client:
        root='/resource-development/issues'
        created=client.post(root,json=dict(source_message_id=str(data['messages']['direct'].id),category='problem',content='接口收录'))
        assert created.status_code==200,created.text
        row=created.json()
        assert client.put(root+'/'+row['id'],json=dict(content='修改',revision=1,proposer_id=str(actor[0].id))).status_code==422
        actor[0]=data['users']['executor']
        assert client.get(root+'/'+row['id']).status_code==404
        actor[0]=data['users']['collector']
        added=client.post(root+'/'+row['id']+'/tasks',json=dict(revision=1,content='接口任务',executor_id=str(data['users']['executor'].id)))
        assert added.status_code==200,added.text
        row=added.json();actor[0]=data['users']['executor']
        assert client.get(root+'/access').json()['can_enter']
        assert client.get(root+'/'+row['id']).status_code==200
        assert client.put(root+'/'+row['id'],json=dict(content='越权',revision=row['revision'])).status_code==403
        assert client.get(root+'/'+row['id']+'/source').json()['available'] is False
        actor[0]=data['users']['inactive']
        assert client.get(root+'/access').status_code==403


def test_timestamps_do_not_depend_on_database_timezone(environment):
    db,data=environment
    import resource_issue_service as service
    from resource_issue_models import DevelopmentIssue
    db.execute(text("SET LOCAL timezone = 'UTC'"))
    row=create(db,data)
    db.expire_all();stored=db.get(DevelopmentIssue,row['id'])
    assert stored.created_at.tzinfo is not None
    assert service.snapshot(stored)['created_at']==row['created_at']
