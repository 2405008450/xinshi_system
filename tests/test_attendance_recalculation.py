"""班次正式变更后的全链路核算；仅使用内存 SQLite。"""
from copy import deepcopy
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event

from test_chat_participant_access import environment
from test_monthly_shift import setup, payload, sync
from test_attendance import at
from test_attendance_clock import punch, out
from attendance_models import AttendanceClockSession as Clock, AttendanceDay, AttendanceLeave
from employee_employment import EmployeeEmployment
from models import EmployeeLeave
import attendance_clock as clock
import attendance_service as attendance
import attendance_policy as policy
import attendance_annual_leave as annual
import attendance_comp_time as comp
import fixed_shift
import weekly_shift as weekly
import weekly_shift_publication as publication
from attendance_recalculation import calculation_scope, project_rows

WEEK = '2026-11-02'
DAY = date(2026, 11, 2)


def change_week(db, users, shift, publish=True, week=WEEK):
    admin, person, _ = users
    plan = weekly.get_plan(db, admin, week)
    if plan['published'] and not plan['can_edit']:
        publication.enable_edit(db, admin, week, publication.SyncWrite(
            revision=plan['revision'], publication_revision=plan['publication_revision'], fixed_revision=plan['fixed_revision']))
    plan = weekly.get_plan(db, admin, week)
    weekly.save_plan(db, admin, week, weekly.WeeklyPlanWrite(
        revision=plan['revision'], assignments=payload(person, shift=shift).assignments))
    if publish:
        sync(db, admin, week)


@pytest.fixture
def prepared(environment, monkeypatch):
    db, users = environment
    setup(db, users)
    for module in (fixed_shift, annual, comp):
        monkeypatch.setattr(module, 'now', lambda: at('2026-11-03T12:00'))
    change_week(db, users, 'early_early')
    db.add(EmployeeEmployment(user_id=users[1].id, hire_date=date(2026, 1, 1)))
    db.commit()
    return db, users


def report(db, person):
    return attendance.attendance_report(db, person, DAY, 'month')


def test_screenshot_draft_publish_reverse_and_all_ledgers(prepared, monkeypatch):
    db, users = prepared
    person = users[1]
    record = punch(db, person, monkeypatch, '2026-11-02T08:59:06')
    out(db, person, record, monkeypatch, '2026-11-02T18:54:32')
    row = db.get(Clock, UUID(record['id']))
    original = deepcopy((row.shift_snapshot, row.confirmations, row.check_in, row.check_out))
    assert report(db, person)['totals']['late_minutes'] == 14.1
    assert annual.ledger(db, [person], 2026)[0]['entries'][0]['minutes'] == 14.1
    change_week(db, users, 'early', publish=False)
    assert report(db, person)['totals']['late_minutes'] == 14.1
    sync(db, users[0], WEEK)
    for _ in range(2):
        value = report(db, person)
        assert value['totals']['late_minutes'] == value['totals']['late_leave_minutes'] == 0
        assert value['records'][0]['shift']['code'] == 'early'
        assert value['monthly_policy'][0]['late_count'] == 0
        assert value['records'][0]['raw_overtime_minutes'] == 25.43
        assert value['monthly_balances'][0]['raw_minutes'] == 25.43
        assert annual.ledger(db, [person], 2026)[0]['entries'] == []
        assert comp.balances(db, [person], date(2026, 11, 3))[0]['obligations'] == []
    db.refresh(row)
    assert (row.shift_snapshot, row.confirmations, row.check_in, row.check_out) == original
    assert not db.dirty
    change_week(db, users, 'early_early')
    assert report(db, person)['totals']['late_leave_minutes'] == 14.1
    assert db.query(Clock).count() == 1


def test_fixed_save_immediate_period_scope_and_manual_settlement(prepared, monkeypatch):
    db, users = prepared
    admin, person, _ = users
    change_week(db, users, 'early_early', week='2026-10-26')
    prior = punch(db, person, monkeypatch, '2026-10-26T08:59:06')
    out(db, person, prior, monkeypatch, '2026-10-26T18:00')
    current = punch(db, person, monkeypatch, '2026-11-02T08:59:06')
    annual.adjustment(db, admin, annual.SettlementWrite(client_id=uuid4(), source_kind='lateness', source_id=current['id'], mode='wage', revision=0, reason='人事核准扣工资'))
    audit = db.query(annual.LeaveSettlementAudit).one()
    audit_before = deepcopy(audit.before_snapshot)
    events = []
    import notification_ws
    monkeypatch.setattr(notification_ws, 'broadcast_to_users', lambda users, value: events.append(value))
    fixed_shift.save_config(db, admin, payload(person, shift='early'))
    assert events == [{'type': 'attendance_schedule_changed'}]
    assert publication.published_plan(db,person,WEEK,mine=True)['assignment']['shift'] == 'early'
    assert clock.serialize(db.get(Clock, UUID(current['id'])))['late_minutes'] == 0
    assert clock.serialize(db.get(Clock, UUID(prior['id'])))['late_minutes'] == 14.1
    fixed_shift.save_config(db, admin, payload(person, revision=1, shift='early_early'))
    entries = annual.ledger(db, [person], 2026)[0]['entries']
    restored = next(item for item in entries if item['source_id'] == current['id'])
    assert restored['mode'] == 'wage' and restored['wage_minutes'] == 14.1
    assert audit.before_snapshot == audit_before and db.query(annual.LeaveSettlementAudit).count() == 1


def test_leave_intersection_recomputed_without_changing_application(prepared):
    db, users = prepared
    person = users[1]
    left, right = at('2026-11-02T08:30'), at('2026-11-02T09:30')
    uid = uuid4()
    days = attendance.preview_leave(db, person, attendance.LeaveWindow(start_at=left, end_at=right))['days']
    saved = AttendanceLeave(id=uid, client_id=uuid4(), user_id=person.id, start_at=left, end_at=right, reason='请假', days=days)
    leave = EmployeeLeave(id=uid, employee_id=person.id, employee_name=person.username, start_date=left.replace(tzinfo=None), end_date=right.replace(tzinfo=None), reason='请假', leave_type='请假')
    db.add_all([saved, leave]); db.commit()
    assert report(db, person)['totals']['requested_leave_minutes'] == 60
    original = deepcopy(saved.days)
    change_week(db, users, 'early')
    assert report(db, person)['totals']['requested_leave_minutes'] == 30
    assert annual.ledger(db, [person], 2026)[0]['entries'][0]['minutes'] == 30
    assert comp.balances(db, [person], date(2026, 11, 3))[0]['obligations'][0]['original_minutes'] == 30
    assert attendance.leave_badges(db, [{'user_id': str(person.id)}], DAY, True)[0]['leave_minutes'] == 30
    db.refresh(saved)
    assert saved.days == original and leave.start_date == left.replace(tzinfo=None)


@pytest.mark.parametrize('moment,expected', [('09:15:00', 0), ('09:15:01', .02)])
def test_open_clock_preview_and_fifteen_minute_boundary(prepared, monkeypatch, moment, expected):
    db, users = prepared
    person = users[1]
    change_week(db, users, 'early')
    monkeypatch.setattr(clock, 'now', lambda: at('2026-11-02T' + moment))
    assert clock.today_status(db, person)['check_in_preview']['late_minutes'] == expected
    record = punch(db, person, monkeypatch, '2026-11-02T' + moment)
    change_week(db, users, 'late')
    status = clock.today_status(db, person)
    assert status['record']['id'] == record['id'] and status['record']['late_minutes'] == 0
    assert status['shift']['code'] == 'late'


def test_multiple_to_single_to_flexible_preserves_groups_and_deductions(prepared, monkeypatch):
    db, users = prepared
    admin, person, _ = users
    fixed_shift.save_config(db, admin, fixed_shift.FixedWrite(revision=0, assignments=[{'user_id':person.id, 'department':'customer', 'shift':'fixed_early_early'}]))
    first = punch(db, person, monkeypatch, '2026-11-02T08:30')
    out(db, person, first, monkeypatch, '2026-11-02T12:00')
    second = punch(db, person, monkeypatch, '2026-11-02T13:30', 1)
    out(db, person, second, monkeypatch, '2026-11-02T19:00', dinner_eaten=True)
    fixed_shift.save_config(db, admin, fixed_shift.FixedWrite(revision=1, assignments=[{'user_id':person.id, 'department':'customer', 'shift':'early'}]))
    value = report(db, person)
    assert len(value['records'][0]['sessions']) == 2
    assert value['totals']['late_count'] == 0 and value['totals']['dinner_deduction_minutes'] == 20
    assert value['records'][0]['shift']['recalculation_warning']
    assert value['records'][0]['sessions'][1]['shift']['recalculation_warning']
    fixed_shift.save_config(db, admin, fixed_shift.FixedWrite(revision=2, assignments=[{'user_id':person.id, 'department':'customer', 'shift':'flexible'}]))
    value = report(db, person)
    assert value['totals']['late_minutes'] == value['totals']['raw_overtime_minutes'] == 0
    assert value['totals']['dinner_deduction_minutes'] == 20 and db.query(Clock).count() == 2


def test_remote_to_regular_no_duplicate_lateness_or_dinner(prepared, monkeypatch):
    db, users = prepared
    person = users[1]
    change_week(db, users, 'customer_remote')
    first = punch(db, person, monkeypatch, '2026-11-02T10:30')
    out(db, person, first, monkeypatch, '2026-11-02T19:00', dinner_eaten=True, deduct_invalid_time=False)
    second = punch(db, person, monkeypatch, '2026-11-02T21:00', 1)
    out(db, person, second, monkeypatch, '2026-11-02T23:00', dinner_eaten=True, deduct_invalid_time=False)
    change_week(db, users, 'early')
    value = report(db, person)
    assert value['totals']['late_count'] == 1 and value['totals']['late_minutes'] == 75
    assert value['totals']['dinner_deduction_minutes'] == 20
    assert len(value['records'][0]['sessions']) == 2


def test_missing_schedule_legacy_and_company_overtime_keep_evidence(prepared):
    db, users = prepared
    person = users[2]
    old = AttendanceDay(user_id=person.id, day=DAY, check_in=at('2026-11-02T09:30'), shift_snapshot={'code':'early', 'label':'早班', 'periods':['09:00–12:00', '13:30–18:30']})
    db.add(old); db.commit()
    value = attendance.serialize_day(old)
    assert value['late_minutes'] == 15 and value['shift']['recalculation_warning']
    change_week(db, users, 'late')
    assert attendance.serialize_day(old)['late_minutes'] == 15


def test_batch_resolution_shared_with_nested_policy_calls(prepared, monkeypatch):
    db, users = prepared
    person = users[1]
    rows = [Clock(user_id=person.id, day=DAY, segment=index, check_in=at('2026-11-02T09:00') if index == 0 else at('2026-11-02T14:00'), shift_snapshot=clock.snapshot({'code':'flexible','periods':[], 'flexible':True}, index), confirmations={}) for index in (0, 1)]
    db.add_all(rows); db.commit()
    calls = []
    real = attendance.shifts_for
    monkeypatch.setattr(attendance, 'shifts_for', lambda db, people, day, **kwargs: (calls.append((len(people), day)), real(db, people, day, **kwargs))[1])
    @calculation_scope
    def evaluate(db):
        projected = project_rows(db, rows)
        policy.monthly(db, [person.id], DAY, DAY, balances=[])
        return projected
    projected = evaluate(db)
    assert len(calls) == 1 and projected[1].shift_snapshot['continuation']
    assert not db.dirty


def test_shift_change_keeps_cross_day_start_adjustment(prepared, monkeypatch):
    db, users = prepared
    person = users[1]
    first = punch(db, person, monkeypatch, '2026-11-02T08:59:06')
    out(db, person, first, monkeypatch, '2026-11-03T09:45', dinner_eaten=True,
        cross_day_reason='持续处理客户紧急事项', next_start=at('2026-11-03T10:00'))
    second = punch(db, person, monkeypatch, '2026-11-03T10:16')
    change_week(db, users, 'early')
    result = clock.serialize(db.get(Clock, UUID(second['id'])))
    assert result['late_minutes'] == 1
    assert result['shift']['late_start_at'] == '2026-11-03T10:00:00+08:00'
    assert result['shift']['start_adjustment_id']
    assert report(db, person)['totals']['dinner_deduction_minutes'] == 20


def test_existing_clock_correction_uses_new_shift_without_false_conflict(prepared, monkeypatch):
    import attendance_corrections as correction
    db, users = prepared
    admin, person, _ = users
    record = punch(db, person, monkeypatch, '2026-11-02T09:30')
    request = correction.submit(db, person, correction.CorrectionWrite(
        client_id=uuid4(), day=DAY, kind='in', record_id=record['id'],
        requested_at=at('2026-11-02T09:00'), reason='实际到岗后忘记打卡',
        early_work_confirmed=False, breakfast_after_eating=True))
    change_week(db, users, 'early')
    result = correction.confirm(db, admin, request['record']['id'])
    row = db.get(Clock, UUID(record['id']))
    assert result['record']['status'] == 'confirmed' and clock.serialize(row)['late_minutes'] == 0
    assert row.shift_snapshot['code'] == 'early_early'
    assert result['record']['history'][-1]['before']['check_in'] != result['record']['history'][-1]['after']['check_in']


def test_schedule_query_count_does_not_grow_with_attendance_dates(prepared):
    db, users = prepared
    person = users[1]
    fixed_shift.save_config(db, users[0], payload(person, shift='early'))
    rows = [Clock(user_id=person.id, day=DAY + timedelta(days=index), segment=0,
                  check_in=at(f'{DAY + timedelta(days=index)}T09:00'),
                  shift_snapshot=clock.snapshot({'code':'early','periods':['09:00–12:00','13:30–18:30']}, 0),
                  confirmations={}) for index in range(31)]
    db.add_all(rows); db.commit()
    queries = []
    def count(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith('SELECT'):
            queries.append(statement)
    event.listen(db.bind, 'before_cursor_execute', count)
    try:
        project_rows(db, rows[:1])
        single = len(queries)
        queries.clear()
        project_rows(db, rows)
        assert len(queries) == single, (single, len(queries))
    finally:
        event.remove(db.bind, 'before_cursor_execute', count)
