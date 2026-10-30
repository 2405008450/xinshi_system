"""仅使用内存 SQLite：三级树、并发版本、人员范围和追加式历史。"""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import inspect
from test_chat_participant_access import environment
import technical_development as service


def payload(owner, executor, name='开发任务', **extra):
    return service.TaskCreate(name=name, arranger_id=owner.id, executor_id=executor.id, **extra)


@pytest.fixture
def setup(environment):
    db, users = environment
    owner, executor, outsider = users
    owner.full_name = '赵震锋'
    owner.department = 'IT部'
    outsider.full_name = '运坚'
    executor.department = 'IT部'
    db.commit()
    return db, users


def test_people_priority_and_technical_membership(setup):
    db, (owner, executor, outsider) = setup
    from department_models import Department, DepartmentMember
    dept = Department(id=uuid4(), name='技术部')
    db.add(dept); db.flush()
    db.add(DepartmentMember(department_id=dept.id, user_id=outsider.id)); db.commit()
    options = service.people(db)
    assert [item['name'] for item in options['arrangers']][:2] == ['赵震锋', '运坚']
    assert {item['id'] for item in options['executors']} == {owner.id, executor.id, outsider.id}
    owner.is_active = False; db.commit()
    assert owner.id not in {item['id'] for item in service.people(db)['arrangers']}
    with pytest.raises(HTTPException) as denied:
        service.list_tasks(db, owner)
    assert denied.value.status_code == 403


def test_three_levels_reparenting_and_cycle_rejected(setup):
    db, (owner, executor, _) = setup
    a = service.create_task(db, owner, payload(owner, executor, 'A'))
    b = service.create_task(db, owner, payload(owner, executor, 'B'))
    b = service.update_task(db, owner, b['id'], service.TaskMove(parent_id=a['id'], revision=b['revision']))
    c = service.create_task(db, owner, payload(owner, executor, 'C', parent_id=b['id']))
    for task_id, parent_id, revision in [(a['id'], c['id'], a['revision']), (b['id'], b['id'], b['revision'])]:
        with pytest.raises(HTTPException) as invalid:
            service.update_task(db, owner, task_id, service.TaskMove(parent_id=parent_id, revision=revision))
        assert invalid.value.status_code == 422
    with pytest.raises(HTTPException):
        service.create_task(db, owner, payload(owner, executor, '第四级', parent_id=c['id']))
    d = service.create_task(db, owner, payload(owner, executor, 'D'))
    # 带两级下属的 A 不能整体移到 D 下。
    with pytest.raises(HTTPException):
        service.update_task(db, owner, a['id'], service.TaskMove(parent_id=d['id'], revision=1))
    moved = service.update_task(db, owner, b['id'], service.TaskMove(parent_id=None, revision=b['revision']))
    assert moved['parent_id'] is None
    assert service.detail(db, owner, c['id'])['parent_id'] == b['id']
    with pytest.raises(HTTPException):
        service.update_task(db, owner, a['id'], service.TaskMove(parent_id=uuid4(), revision=1))


def test_progress_rollback_reason_and_immutable_history(setup):
    db, (owner, executor, _) = setup
    task = service.create_task(db, owner, payload(owner, executor))
    assert task['progress'] == 0 and task['progress_updated_at'] is None
    first = service.update_task(db, executor, task['id'], service.ProgressWrite(percentage=90, content='联调完成', revision=1))
    assert first['progress'] == 90 and first['progress_updated_at'].utcoffset().total_seconds() == 8 * 3600
    with pytest.raises(HTTPException) as rejected:
        service.update_task(db, owner, task['id'], service.ProgressWrite(percentage=80, reason='  ', revision=2))
    assert rejected.value.status_code == 422
    assert service.detail(db, owner, task['id'])['progress'] == 90
    second = service.update_task(db, owner, task['id'], service.ProgressWrite(percentage=80, content='重新联调', reason='发现遗漏用例', revision=2))
    assert second['progress'] == 80 and second['revision'] == 3
    history = second['progress_history']
    assert [(h['previous_percentage'], h['percentage']) for h in history] == [(90, 80), (0, 90)]
    assert history[0]['reason'] == '发现遗漏用例' and history[0]['author_name'] == '赵震锋'
    assert history[1]['author_id'] == executor.id
    with pytest.raises(HTTPException) as stale:
        service.update_task(db, owner, task['id'], service.ProgressWrite(percentage=100, revision=2))
    assert stale.value.status_code == 409
    assert len(service.detail(db, owner, task['id'])['progress_history']) == 2


@pytest.mark.parametrize('percentage', [0, 101, 80.5, True])
def test_progress_rejects_invalid_numbers(percentage):
    with pytest.raises(ValidationError):
        service.ProgressWrite(percentage=percentage, revision=1)


def test_feedback_by_everyone_and_task_fields_versions(setup):
    db, (owner, executor, outsider) = setup
    task = service.create_task(db, owner, payload(owner, executor, due_at='2026-11-01T08:00:00Z'))
    outsider.department = 'IT部'; db.commit()
    assert task['due_at'].hour == 16
    for person in (executor, outsider):
        service.add_feedback(db, person, task['id'], service.FeedbackWrite(content=f'{person.username} 的意见'))
    value = service.detail(db, owner, task['id'])
    assert {record['author_id'] for record in value['feedback']} == {executor.id, outsider.id}
    assert all(record['created_at'].utcoffset().total_seconds() == 28800 for record in value['feedback'])
    updated = service.update_task(db, owner, task['id'], service.TaskUpdate(**{**payload(owner, executor).model_dump(exclude={'parent_id'}), 'adjustment': '按反馈调整', 'notes': '备注'}, revision=1))
    assert updated['adjustment'] == '按反馈调整' and len(updated['feedback']) == 2
    with pytest.raises(HTTPException):
        service.update_task(db, owner, task['id'], service.TaskUpdate(**payload(owner, executor).model_dump(exclude={'parent_id'}), revision=1))
    with pytest.raises(HTTPException):
        service.create_task(db, owner, service.TaskCreate(name='错误执行人', arranger_id=owner.id, executor_id=uuid4()))
    with pytest.raises(ValidationError):
        service.FeedbackWrite(content='  ')


def test_create_only_migration_is_idempotent(setup):
    db, (owner, _, _) = setup
    from tools.apply_technical_development_migration import apply_migration
    for table in reversed(service.TABLES):
        table.drop(db.connection())
    db.commit()
    def columns():
        return [(column['name'], str(column['type']), column['nullable'], column['default']) for column in inspect(db.connection()).get_columns('app_user')]
    before = columns()
    apply_migration(db.connection()); apply_migration(db.connection()); db.commit()
    assert columns() == before
    assert db.get(service.AppUser, owner.id) is not None
    assert all(inspect(db.connection()).has_table(table.name) for table in service.TABLES)
    assert service.list_tasks(db, owner) == dict(enabled=True, items=[])


def test_http_contract_and_no_client_authorship(setup):
    db, (owner, executor, outsider) = setup
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.technical_development import router
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: owner
    client = TestClient(app)
    created = client.post('/technical-development/tasks', json=payload(owner, executor).model_dump(mode='json'))
    assert created.status_code == 200
    row = created.json()
    assert row['created_at'].endswith('+08:00')
    base = f"/technical-development/tasks/{row['id']}"
    assert client.post(base + '/progress', json=dict(percentage=90, revision=1)).status_code == 200
    assert client.post(base + '/progress', json=dict(percentage=80, revision=2)).status_code == 422
    assert client.post(base + '/progress', json=dict(percentage=80, revision=2, reason='修复缺陷')).status_code == 200
    assert client.post(base + '/progress', json=dict(percentage=100, revision=1)).status_code == 409
    assert client.post(base + '/feedback', json=dict(content='意见', author_id=str(outsider.id))).status_code == 422
    feedback = client.post(base + '/feedback', json=dict(content='意见')).json()['feedback'][0]
    assert feedback['author_id'] == str(owner.id) and feedback['created_at'].endswith('+08:00')
    owner.is_deleted = True; db.commit()
    assert client.get('/technical-development/tasks').status_code == 403
