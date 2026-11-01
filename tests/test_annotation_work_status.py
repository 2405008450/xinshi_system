"""状态汇报、累计用时、提醒及报告保护；仅访问隔离 SQLite。"""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event

from test_chat_participant_access import environment
from test_annotation_today_tasks import project
import annotation_work_status as service
from annotation_work_status_models import AnnotationWorkDay, AnnotationWorkSubmission, AnnotationWorkReminder, AnnotationWorkAvailability
from annotation_ops_models import AnnotationProjectStatusHistory
from task_models import DailyReport, DailyReportItem
from task_schemas import DailyReportSaveRequest
from chat_time import BUSINESS_TIMEZONE


@pytest.fixture
def setup(environment, monkeypatch):
    db, (owner, member, outsider) = environment
    row = project(db, owner, member)
    clock = [datetime(2026, 11, 1, 11, tzinfo=BUSINESS_TIMEZONE)]
    monkeypatch.setattr(service, 'now', lambda: clock[0])
    return db, member, outsider, row, clock


def arrange(revision=0, status='in_progress'):
    return service.ArrangementWrite(revision=revision, arrangement_status=status, remaining_time='1_2h')


def submission(revision=1, slot='11', minutes=60):
    return service.SubmissionWrite(**arrange(revision).model_dump(), slot=slot,
        progress_note='已完成样本检查', cumulative_minutes=minutes)


def test_selected_projects_and_reset_next_day(setup):
    db, member, _, row, clock = setup
    before = service.context(db, member)
    assert before['items'][0]['entered_at'] is None
    saved = service.save_arrangement(db, member, row.id, arrange())
    assert saved['revision'] == 1 and saved['entered_at'].utcoffset().total_seconds() == 28800
    service.save_arrangement(db, member, row.id, arrange(1, 'not_today'))
    assert service.context(db, member)['items'][0]['entered_at'] is not None
    clock[0] += timedelta(days=1)
    assert service.context(db, member)['items'][0]['entered_at'] is None
    assert service.context(db, member)['items'][0]['revision'] == 0


def test_cumulative_minutes_single_report_and_project_progress(setup):
    db, member, _, row, clock = setup
    service.save_arrangement(db, member, row.id, arrange())
    service.submit(db, member, row.id, submission())
    clock[0] = clock[0].replace(hour=15)
    service.submit(db, member, row.id, submission(2, '15', 120))
    clock[0] = clock[0].replace(hour=18)
    service.submit(db, member, row.id, submission(3, 'end_shift', 180))
    report = db.query(DailyReport).one()
    assert len(report.items) == 1
    item = report.items[0]
    assert item.duration_minutes == 180  # 不是60+120+180。
    assert item.task_type == '项目工作'
    assert item.display_metadata['report_types'] == ['标注项目']
    assert item.display_metadata['order_no'] == row.order_no
    assert '11:00' in item.progress_content and '15:00' in item.progress_content and '下班' in item.progress_content
    progress = db.query(AnnotationProjectStatusHistory).all()
    assert len(progress) == 3 and all(entry.entry_kind == 'progress' for entry in progress)
    assert all(entry.to_status == row.project_status for entry in progress)
    assert db.query(AnnotationWorkSubmission).count() == 3


def test_rejects_stale_duplicate_decreasing_future_and_outsider(setup):
    db, member, outsider, row, clock = setup
    service.save_arrangement(db, member, row.id, arrange())
    with pytest.raises(HTTPException, match='') as future:
        service.submit(db, member, row.id, submission(1, '15'))
    assert future.value.status_code == 422
    db.rollback()
    service.submit(db, member, row.id, submission())
    for payload in (submission(), submission(2)):
        with pytest.raises(HTTPException) as duplicate:
            service.submit(db, member, row.id, payload)
        assert duplicate.value.status_code == 409
        db.rollback()
    clock[0] = clock[0].replace(hour=15)
    with pytest.raises(HTTPException) as decrease:
        service.submit(db, member, row.id, submission(2, '15', 30))
    assert decrease.value.status_code == 422
    db.rollback()
    with pytest.raises(HTTPException) as denied:
        service.save_arrangement(db, outsider, row.id, arrange())
    assert denied.value.status_code == 404
    db.rollback()
    assert db.query(AnnotationWorkSubmission).count() == 1


def test_finalized_report_and_failure_are_atomic(setup, monkeypatch):
    db, member, _, row, _ = setup
    service.save_arrangement(db, member, row.id, arrange())
    service.submit(db, member, row.id, submission())
    report = db.query(DailyReport).one()
    report.status = 'finalized'
    db.commit()
    with pytest.raises(HTTPException):
        service.submit(db, member, row.id, submission(2, 'end_shift', 120))
    db.rollback()
    assert db.query(AnnotationWorkSubmission).count() == 1
    report.status = 'draft'
    db.commit()
    with monkeypatch.context() as patch:
        patch.setattr(db, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('模拟提交失败')))
        with pytest.raises(RuntimeError):
            service.submit(db, member, row.id, submission(2, 'end_shift', 120))
    db.rollback()
    assert db.query(AnnotationWorkSubmission).count() == 1
    assert db.query(AnnotationProjectStatusHistory).count() == 1
    assert db.query(DailyReportItem).one().duration_minutes == 60
    assert db.query(AnnotationWorkDay).one().revision == 2


def test_old_report_window_and_refresh_keep_latest_cumulative(setup, monkeypatch):
    import task_service
    db, member, _, row, clock = setup
    service.save_arrangement(db, member, row.id, arrange())
    service.submit(db, member, row.id, submission())
    item = db.query(DailyReportItem).one()
    stale = {key:getattr(item,key) for key in ['source_type','source_id','task_type','task_name','progress_content','duration_minutes','display_metadata']}
    clock[0] = clock[0].replace(hour=15)
    service.submit(db, member, row.id, submission(2, '15', 120))
    monkeypatch.setattr(task_service, 'derive_daily_report_items', lambda *args: [])
    preview = task_service.preview_daily_report(db, member, clock[0].date(), refresh=True)
    assert len(preview['items']) == 1 and preview['items'][0]['duration_minutes'] == 120
    def set_id(mapper, connection, target):
        if target.id is None: target.id=uuid4()
    event.listen(DailyReportItem, 'before_insert', set_id)
    try:
        report = task_service.save_daily_report(db, member, clock[0].date(), DailyReportSaveRequest(items=[stale]))
        assert report.items[0].duration_minutes == 120
        report = task_service.save_daily_report(db, member, clock[0].date(), DailyReportSaveRequest(items=[]))
        assert len(report.items) == 1 and report.items[0].duration_minutes == 120
    finally:
        event.remove(DailyReportItem, 'before_insert', set_id)


def test_reminder_weekend_duty_and_multiple_windows(setup, monkeypatch):
    db, member, _, _, clock = setup
    monkeypatch.setattr(service, 'on_duty', lambda *args: True)
    assert clock[0].weekday() == 6
    assert service.claim_reminder(db, member)['slot'] == '11'
    assert service.claim_reminder(db, member) == {'remind': False}
    clock[0] = clock[0].replace(hour=15)
    assert service.claim_reminder(db, member)['slot'] == '15'
    clock[0] = clock[0].replace(hour=18)
    monkeypatch.setattr(service, 'on_duty', lambda *args: False)
    assert service.claim_reminder(db, member) == {'remind': False}
    assert db.query(AnnotationWorkReminder).count() == 2


def test_duty_uses_shift_intervals_checkout_and_leave(setup, monkeypatch):
    import attendance_service
    from attendance_models import AttendanceDay
    from models import EmployeeLeave
    db, member, _, _, clock = setup
    monkeypatch.setattr(attendance_service, 'shift_for', lambda *args: None)
    assert not service.on_duty(db, member, clock[0])
    monkeypatch.setattr(attendance_service, 'shift_for', lambda *args: {'periods':['09:00-12:00']})
    assert service.on_duty(db, member, clock[0])
    attendance = AttendanceDay(id=uuid4(), user_id=member.id, day=clock[0].date(), check_out=clock[0])
    db.add(attendance);db.commit()
    assert not service.on_duty(db, member, clock[0])
    attendance.check_out=None;db.commit()
    leave=EmployeeLeave(id=uuid4(),employee_id=member.id,start_date=clock[0].replace(tzinfo=None)-timedelta(hours=1),end_date=clock[0].replace(tzinfo=None)+timedelta(hours=1))
    db.add(leave);db.commit()
    assert not service.on_duty(db, member, clock[0])


def test_idle_required_estimate_and_report_sync_without_project(setup):
    db, member, outsider, _, _ = setup
    with pytest.raises(ValidationError):
        service.AvailabilityWrite(slot='11', revision=0, is_idle=True)
    for estimate in service.IDLE_LABELS:
        revision = db.query(AnnotationWorkAvailability).first().revision if db.query(AnnotationWorkAvailability).first() else 0
        result = service.save_availability(db, member, service.AvailabilityWrite(slot='11', revision=revision, is_idle=True, expected_idle_time=estimate))
        assert result['expected_idle_time'] == estimate
    assert not db.query(DailyReportItem).count()
    assert not db.query(AnnotationWorkSubmission).count()
    assert '空闲状态 是' in db.query(DailyReport).one().supplemental_note
    result = service.save_availability(db, member, service.AvailabilityWrite(slot='11', revision=5, is_idle=False, expected_idle_time='under_30'))
    assert result['expected_idle_time'] is None
    assert db.query(DailyReport).one().supplemental_note.count('11:00') == 1
    assert service.context(db, member)['availability']['11']['is_idle'] is False
    with pytest.raises(HTTPException) as denied:
        service.save_availability(db, outsider, service.AvailabilityWrite(slot='11',revision=0,is_idle=False))
    assert denied.value.status_code == 403


def test_migration_repeatable_only_creates_new_tables(environment):
    from tools.apply_annotation_work_status_migration import apply_migration
    db, _ = environment
    models = [AnnotationWorkAvailability, AnnotationWorkReminder, AnnotationWorkSubmission, AnnotationWorkDay]
    for model in models:model.__table__.drop(db.connection())
    apply_migration(db.connection());apply_migration(db.connection())
    assert service.ready(db)


@pytest.mark.parametrize('hour', [11, 15, 18, 21])
def test_all_reminder_checkpoints(setup, monkeypatch, hour):
    db, member, _, _, clock = setup
    clock[0] = clock[0].replace(hour=hour, minute=0)
    monkeypatch.setattr(service, 'on_duty', lambda *args: True)
    assert service.claim_reminder(db, member)['slot'] == str(hour)
    assert service.claim_reminder(db, member)['remind'] is False


def test_no_added_time_does_not_double_count(setup):
    db, member, _, row, clock = setup
    service.save_arrangement(db, member, row.id, arrange())
    service.submit(db, member, row.id, submission())
    clock[0] = clock[0].replace(hour=15)
    service.submit(db, member, row.id, submission(2, '15', 60))
    assert db.query(DailyReportItem).one().duration_minutes == 60


def test_report_save_preserves_idle_summary(setup, monkeypatch):
    import task_service
    db, member, _, _, clock = setup
    service.save_availability(db, member, service.AvailabilityWrite(slot='11',revision=0,is_idle=True,expected_idle_time='under_30'))
    monkeypatch.setattr(task_service, 'derive_daily_report_items', lambda *args: [])
    report = task_service.save_daily_report(db, member, clock[0].date(), DailyReportSaveRequest(items=[],supplemental_note='其他说明'))
    assert '其他说明' in report.supplemental_note
    assert '空闲状态 是，预计空闲时间：30分钟内' in report.supplemental_note
