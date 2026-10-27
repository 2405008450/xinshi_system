"""项目安排权限、完整报告校验及完成事务；只使用内存 SQLite。"""
from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_chat_participant_access import environment
import project_arrangement as service


def create(db, owner, assignee):
    from models import TranslationProject
    project = TranslationProject(id=uuid4(), order_no='TP-TEST-001', project_name='隔离安排项目', created_by=owner.id)
    db.add(project); db.commit()
    payload = service.AssignmentBatch(items=[{'assignee_id': assignee.id, 'content': '核对稿件', 'work_date': date(2026, 10, 25)}])
    return project, service.create_assignments(db, owner, project.id, payload)[0]


def completion(revision=1):
    return service.TaskComplete(revision=revision, item={
        'source_type': 'manual', 'task_type': '项目工作', 'task_name': '隔离安排项目',
        'progress_content': '核对稿件并确认术语', 'duration_minutes': 66,
        'display_metadata': {'report_types': ['笔译项目'], 'order_no': 'TP-TEST-001', 'quantity': '2', 'quantity_unit': '份'},
    })


def test_assign_edit_and_optimistic_lock(environment):
    db, (owner, member, outsider) = environment
    _, task = create(db, owner, member)
    assert task['status'] == 'pending' and task['estimated_minutes'] == 0
    with pytest.raises(HTTPException) as denied:
        service.edit_task(db, outsider, task['id'], service.TaskEdit(revision=1, content='越权'))
    assert denied.value.status_code == 403
    saved = service.edit_task(db, member, task['id'], service.TaskEdit(revision=1, estimated_minutes=66, actual_minutes=30, status='in_progress'))
    assert saved['revision'] == 2 and saved['status'] == 'in_progress'
    with pytest.raises(HTTPException) as stale:
        service.edit_task(db, member, task['id'], service.TaskEdit(revision=1, content='过期'))
    assert stale.value.status_code == 409
    with pytest.raises(HTTPException):
        service.edit_task(db, member, task['id'], service.TaskEdit(revision=2, status='completed'))


def test_complete_requires_all_report_fields_and_assignee(environment):
    db, (owner, member, outsider) = environment
    _, task = create(db, owner, member)
    invalid = completion().model_dump()
    invalid['item']['display_metadata']['quantity_unit'] = ''
    with pytest.raises(ValidationError):
        service.TaskComplete.model_validate(invalid)
    with pytest.raises(HTTPException):
        service.complete_task(db, outsider, task['id'], completion())
    assert db.get(service.ProjectArrangement, task['id']).status == 'pending'
    saved = service.complete_task(db, member, task['id'], completion())
    assert saved['status'] == 'completed' and saved['actual_minutes'] == 66
    assert saved['completed_at'].utcoffset().total_seconds() == 28800
    report = db.query(service.DailyReport).filter_by(user_id=member.id).one()
    assert report.status == 'draft' and len(report.items) == 1
    item = report.items[0]
    assert item.progress_content == '核对稿件并确认术语'
    assert item.display_metadata['order_no'] == 'TP-TEST-001'
    assert item.display_metadata['arrangement_id'] == str(task['id'])
    with pytest.raises(HTTPException):
        service.complete_task(db, member, task['id'], completion(saved['revision']))
    assert db.query(service.DailyReportItem).count() == 1


def test_finalized_report_does_not_complete_task(environment):
    db, (owner, member, _) = environment
    _, task = create(db, owner, member)
    db.add(service.DailyReport(id=uuid4(), user_id=member.id, report_date=service.report_business_date(service.now()), status='finalized'))
    db.commit()
    with pytest.raises(HTTPException) as denied:
        service.complete_task(db, member, task['id'], completion())
    assert denied.value.status_code == 409
    assert db.get(service.ProjectArrangement, task['id']).status == 'pending'
    assert db.query(service.DailyReportItem).count() == 0


def test_review_uses_report_scope_and_department_filter(environment):
    from work_report_access import AccessRuleWrite, save_rule
    from routers.project_arrangements import tasks
    db, (owner, member, outsider) = environment
    owner.username='williamzhao'; db.commit()
    _, first = create(db, owner, member)
    create(db, owner, outsider)
    save_rule(db, owner, AccessRuleWrite(name='任务查看范围', viewer_ids=[owner.id], sender_ids=[member.id]))
    data = tasks(date(2026,10,25), True, None, None, [], 1, 10, db, owner)
    assert data['total'] == 1 and data['items'][0]['id'] == first['id']
    assert tasks(date(2026,10,25), True, outsider.id, None, [], 1, 10, db, owner)['total'] == 0
    assert tasks(date(2026,10,25), False, None, None, [], 1, 10, db, outsider)['total'] == 1


def test_migration_is_repeatable(environment):
    from tools.apply_project_arrangement_migration import apply_migration
    db, _ = environment
    apply_migration(db.connection()); apply_migration(db.connection())
    assert service.ready(db)


def test_stale_report_editor_cannot_remove_completed_task(environment, monkeypatch):
    import task_service
    from sqlalchemy import event
    db, (owner, member, _) = environment
    _, task = create(db, owner, member)
    service.complete_task(db, member, task['id'], completion())
    monkeypatch.setattr(task_service, 'derive_daily_report_items', lambda *args: [])
    # 隔离 SQLite 不执行 PostgreSQL gen_random_uuid 默认值。
    def assign_test_id(mapper, connection, target):
        if target.id is None:
            target.id = uuid4()
    event.listen(service.DailyReportItem, 'before_insert', assign_test_id)
    try:
        report = task_service.save_daily_report(db, member, service.report_business_date(service.now()), service.DailyReportSaveRequest(items=[]))
    finally:
        event.remove(service.DailyReportItem, 'before_insert', assign_test_id)
    assert len(report.items) == 1
    assert report.items[0].display_metadata['arrangement_id'] == str(task['id'])


def test_commit_failure_rolls_back_report_and_completion(environment, monkeypatch):
    db, (owner, member, _) = environment
    _, task = create(db, owner, member)
    def failed_commit():
        raise RuntimeError('模拟存储失败')
    with monkeypatch.context() as patch:
        patch.setattr(db, 'commit', failed_commit)
        with pytest.raises(RuntimeError):
            service.complete_task(db, member, task['id'], completion())
    db.rollback()
    assert db.get(service.ProjectArrangement, task['id']).status == 'pending'
    assert db.query(service.DailyReport).count() == 0
    assert db.query(service.DailyReportItem).count() == 0
