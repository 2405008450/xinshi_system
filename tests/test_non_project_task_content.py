"""非项目任务具体内容的保存、周期复制和权限，使用隔离 SQLite。"""
from uuid import uuid4
import pytest
from sqlalchemy import event, inspect
from test_chat_participant_access import environment
from task_models import NonProjectTask, NonProjectTaskRecurrence, NonProjectTaskEvent, NonProjectTaskContent
from task_schemas import NonProjectTaskCreate, NonProjectTaskUpdate, RecurrenceCreate, RecurrenceResponse
import task_service as service


def prepare(db, monkeypatch):
    @event.listens_for(db, 'before_flush')
    def ids(session, *_):
        for row in session.new:
            if isinstance(row, (NonProjectTask, NonProjectTaskRecurrence, NonProjectTaskEvent)) and row.id is None:
                row.id = uuid4()
    monkeypatch.setattr(service, '_ensure_assignee_allowed', lambda *args: None)
    monkeypatch.setattr(service, '_can_assign', lambda *args: False)


def test_content_roundtrip_does_not_replace_remark_and_checks_access(environment, monkeypatch):
    db, (owner, other, _) = environment
    prepare(db, monkeypatch)
    task = service.create_non_project_task(db, owner, NonProjectTaskCreate(task_type='非项目工作', task_name='汇总资料', specific_task='核对表格\n整理词汇', remark='原备注'))
    db.expire_all()
    data = service.serialize_non_project_task(service.get_non_project_task(db, task.id))
    assert data['specific_task'] == '核对表格\n整理词汇' and data['remark'] == '原备注'
    with pytest.raises(PermissionError):
        service.update_non_project_task(db, task.id, other, NonProjectTaskUpdate(specific_task='不得修改'))
    service.update_non_project_task(db, task.id, owner, NonProjectTaskUpdate(task_name='改名'))
    assert task.specific_task == '核对表格\n整理词汇'
    service.update_non_project_task(db, task.id, owner, NonProjectTaskUpdate(specific_task=''))
    db.expire_all()
    assert service.get_non_project_task(db, task.id).specific_task == ''
    assert service.get_non_project_task(db, task.id).remark == '原备注'


def test_recurrence_copies_content_and_legacy_default_is_empty(environment, monkeypatch):
    db, (owner, _, _) = environment
    prepare(db, monkeypatch)
    day = service.business_now().date()
    rule = service.create_recurrence(db, owner, RecurrenceCreate(task_type='非项目工作', task_name='每日整理', specific_task='逐项检查', frequency='daily', start_date=day, end_date=day, remark='周期备注'))
    task = db.query(NonProjectTask).filter_by(recurrence_template_id=rule.id).one()
    assert task.specific_task == '逐项检查'
    assert task.remark == '周期备注'
    assert RecurrenceResponse.model_validate(rule).specific_task == '逐项检查'
    old = service.create_non_project_task(db, owner, NonProjectTaskCreate(task_type='其他', task_name='无新增字段'))
    assert old.specific_task == '' and old.specific_task_content is None


def test_migration_is_repeatable_and_does_not_backfill(environment):
    from tools.apply_non_project_task_content_migration import apply_migration
    db, _ = environment
    NonProjectTaskContent.__table__.drop(db.connection())
    before = set(inspect(db.connection()).get_table_names())
    apply_migration(db.connection()); apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names()) == before | {'non_project_task_content'}
    assert inspect(db.connection()).get_check_constraints('non_project_task_content')
    assert db.query(NonProjectTaskContent).count() == 0
