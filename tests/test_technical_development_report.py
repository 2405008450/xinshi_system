from datetime import datetime, date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_technical_development import environment, setup, payload
from chat_time import BUSINESS_TIMEZONE
import technical_development as tasks
import technical_development_report as reports


def request(**extra):
    return reports.ReportWrite(**(dict(request_id=uuid4(), report_type='开发任务', order_no='DT-261030-001', task_name='开发任务名称', progress_content='开发任务内容', quantity='2.5', quantity_unit='项', duration_minutes=30) | extra))


def test_numbers_daily_unique_stable_and_three_levels(setup, monkeypatch):
    db, (owner, executor, _) = setup
    monkeypatch.setattr(tasks, 'now', lambda: datetime(2026, 10, 30, 23, 59, tzinfo=BUSINESS_TIMEZONE))
    a = tasks.create_task(db, owner, payload(owner, executor))
    b = tasks.create_task(db, owner, payload(owner, executor, parent_id=a['id']))
    c = tasks.create_task(db, owner, payload(owner, executor, parent_id=b['id']))
    assert [a['task_no'], b['task_no'], c['task_no']] == ['DT-261030-001', 'DT-261030-001.001', 'DT-261030-001.001.001']
    monkeypatch.setattr(tasks, 'now', lambda: datetime(2026, 10, 31, 0, 1, tzinfo=BUSINESS_TIMEZONE))
    d = tasks.create_task(db, owner, payload(owner, executor))
    assert d['task_no'] == 'DT-261031-001'
    assert '.' not in tasks.update_task(db, owner, b['id'], tasks.TaskMove(parent_id=None, revision=1))['task_no']
    assert len({row['task_no'] for row in tasks.list_tasks(db, owner)['items']}) == 4


def test_only_department_members_even_active_accounts(setup):
    db, (owner, executor, outsider) = setup
    assert tasks.can_enter(db, owner) and not tasks.can_enter(db, outsider)
    for call in [lambda: tasks.list_tasks(db, outsider), lambda: tasks.create_task(db, outsider, payload(owner, executor))]:
        with pytest.raises(HTTPException) as denied: call()
        assert denied.value.status_code == 403
    row = tasks.create_task(db, owner, payload(owner, executor))
    with pytest.raises(HTTPException): tasks.detail(db, outsider, row['id'])
    with pytest.raises(HTTPException): reports.submit(db, outsider, row['id'], request())
    with pytest.raises(HTTPException): tasks.add_feedback(db, outsider, row['id'], tasks.FeedbackWrite(content='越权'))


def test_append_edited_fields_idempotency_day_boundary_and_refresh(setup, monkeypatch):
    from task_models import DailyReport
    import task_service
    import consultation_work_report
    db, (owner, executor, _) = setup
    monkeypatch.setattr(consultation_work_report, 'publish_report_update', lambda *args: None)
    monkeypatch.setattr(reports, 'now', lambda: datetime(2026, 10, 31, 6, 59, tzinfo=BUSINESS_TIMEZONE))
    task = tasks.create_task(db, owner, payload(owner, executor, content='原始内容'))
    value = request(order_no='用户编辑编号', task_name='用户编辑名称', progress_content='用户编辑内容', report_type='管理工作')
    result = reports.submit(db, owner, task['id'], value)
    assert result['report_date'] == date(2026, 10, 30)
    report = db.get(DailyReport, result['report_id'])
    entry = report.items[0]
    assert entry.duration_minutes == 30
    assert entry.display_metadata['quantity'] == '2.5' and entry.display_metadata['quantity_unit'] == '项'
    assert entry.display_metadata['added_at'] == '2026-10-31T06:59:00+08:00'
    assert entry.task_name == '用户编辑名称' and entry.progress_content == '用户编辑内容'
    assert entry.display_metadata['order_no'] == '用户编辑编号'
    assert entry.display_metadata['report_types'] == ['管理工作']
    assert entry.display_metadata['technical_task_id'] == str(task['id'])
    assert tasks.detail(db, owner, task['id'])['name'] != entry.task_name
    assert reports.submit(db, owner, task['id'], value)['already_saved'] and len(report.items) == 1
    monkeypatch.setattr(task_service, 'derive_daily_report_items', lambda *args: [])
    preview = task_service.preview_daily_report(db, owner, report.report_date, refresh=True)
    assert len(preview['items']) == 1 and preview['items'][0]['display_metadata']['technical_task_id'] == str(task['id'])
    monkeypatch.setattr(reports, 'now', lambda: datetime(2026, 10, 31, 7, 0, tzinfo=BUSINESS_TIMEZONE))
    assert reports.submit(db, owner, task['id'], value)['report_date'] == date(2026, 10, 30)
    assert reports.submit(db, owner, task['id'], request())['report_date'] == date(2026, 10, 31)
    report.status = 'finalized'; db.commit()
    monkeypatch.setattr(reports, 'now', lambda: datetime(2026, 10, 30, 12, 0, tzinfo=BUSINESS_TIMEZONE))
    with pytest.raises(HTTPException) as denied: reports.submit(db, owner, task['id'], request())
    assert denied.value.status_code == 409


def test_migration_backfills_only_new_mapping_and_idempotent(setup):
    from tools.apply_technical_development_number_migration import apply_migration
    db, (owner, executor, _) = setup
    row = tasks.create_task(db, owner, payload(owner, executor))
    original = db.get(tasks.DevelopmentTask, row['id'])
    before = (original.name, original.revision, original.updated_at)
    tasks.DevelopmentReportReceipt.__table__.drop(db.connection())
    tasks.DevelopmentTaskNumber.__table__.drop(db.connection()); db.commit()
    with db.bind.begin() as connection: apply_migration(connection)
    with db.bind.begin() as connection: apply_migration(connection)
    db.expire_all()
    assert db.query(tasks.DevelopmentTaskNumber).count() == 1
    original = db.get(tasks.DevelopmentTask, row['id'])
    assert (original.name, original.revision, original.updated_at) == before


def test_named_members_added_preserving_other_departments(setup):
    from department_models import Department, DepartmentMember
    from tools.configure_technical_department_members import configure
    db, (_, executor, outsider) = setup
    executor.username = 'ethan'; executor.department = '销售'
    outsider.username = 'thomas'; outsider.department = '销售'
    dept = Department(id=uuid4(), name='IT部'); db.add(dept); db.commit()
    assert configure(db, dept.id, 1)['add'] == ['ethan', 'thomas']
    assert db.query(DepartmentMember).count() == 0
    configure(db, dept.id, 1, True); db.commit()
    assert executor.department == outsider.department == '销售'
    assert tasks.can_enter(db, executor) and tasks.can_enter(db, outsider)
    assert configure(db, dept.id, 2, True)['add'] == []


def test_http_endpoints_deny_nonmembers_and_do_not_list_people(setup):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.technical_development import router
    db, (owner, executor, outsider) = setup
    row = tasks.create_task(db, owner, payload(owner, executor))
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: outsider
    client = TestClient(app)
    assert client.get('/technical-development/access').json() == {'can_enter': False}
    base = f"/technical-development/tasks/{row['id']}"
    for path in ['/technical-development/people', '/technical-development/tasks', base, base + '/report']:
        assert client.get(path).status_code == 403
    assert client.post(base + '/feedback', json={'content': '意见'}).status_code == 403
    assert client.post(base + '/progress', json={'percentage': 90, 'revision': 1}).status_code == 403
    assert client.post(base + '/report', json=request().model_dump(mode='json')).status_code == 403


def test_stale_report_save_keeps_added_rows_and_finalization_requires_real_duration(setup, monkeypatch):
    from task_models import DailyReport, DailyReportItem
    from task_schemas import DailyReportSaveRequest
    import task_service
    import consultation_work_report
    db, (owner, executor, _) = setup
    monkeypatch.setattr(consultation_work_report, 'publish_report_update', lambda *args: None)
    row = tasks.create_task(db, owner, payload(owner, executor))
    result = reports.submit(db, owner, row['id'], request())
    report = db.get(DailyReport, result['report_id'])
    # 历史草稿仍可能缺少这些字段，最终确认时继续要求补齐。
    report.items[0].duration_minutes = 0
    report.items[0].display_metadata = {**report.items[0].display_metadata, 'quantity': '', 'quantity_unit': ''}
    db.commit()
    monkeypatch.setattr(task_service, 'derive_daily_report_items', lambda *args: [])
    with pytest.raises(ValueError, match='工作量、单位和耗时'):
        task_service.save_daily_report(db, owner, report.report_date, DailyReportSaveRequest(items=[]), finalize=True)
    original = DailyReportItem
    monkeypatch.setattr(task_service, 'DailyReportItem', lambda **kw: original(id=uuid4(), **kw))
    task_service.save_daily_report(db, owner, report.report_date, DailyReportSaveRequest(items=[]))
    assert len(report.items) == 1 and report.items[0].display_metadata['technical_task_id'] == str(row['id'])


@pytest.mark.parametrize('extra', [dict(progress_content=' '), dict(task_name=' '), dict(order_no=' '), dict(progress_content='data:image/png;base64,x'), dict(quantity=''), dict(quantity=-1), dict(quantity='NaN'), dict(quantity=True), dict(quantity_unit=' '), dict(quantity_unit='其他'), dict(quantity_unit='data:image/png'), dict(duration_minutes=0), dict(duration_minutes=1441), dict(duration_minutes=1.5), dict(report_types=[]), dict(report_types=['未知类型'])])
def test_report_validation(extra):
    with pytest.raises(ValidationError): request(**extra)


def test_complete_report_multiple_types_custom_unit_and_context(setup, monkeypatch):
    from task_models import DailyReport
    import consultation_work_report
    db, (owner, executor, _) = setup
    monkeypatch.setattr(consultation_work_report, 'publish_report_update', lambda *args: None)
    row = tasks.create_task(db, owner, payload(owner, executor))
    value = reports.context(db, owner, row['id'])
    assert value['report_types'] == ['开发任务'] and value['duration_minutes'] is None
    result = reports.submit(db, owner, row['id'], request(report_types=['开发任务', '管理工作'], quantity=0, quantity_unit='其他', quantity_unit_other='接口'))
    entry = db.get(DailyReport, result['report_id']).items[0]
    assert entry.display_metadata['report_types'] == ['开发任务', '管理工作']
    assert entry.display_metadata['quantity'] == 0 and entry.display_metadata['quantity_unit_other'] == '接口'
