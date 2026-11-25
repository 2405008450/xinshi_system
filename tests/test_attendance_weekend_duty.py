"""周末值班使用独立时段；仅运行于内存 SQLite。"""
from datetime import date
from types import SimpleNamespace

import pytest

from test_chat_participant_access import environment
from test_monthly_shift import setup, payload
from test_attendance import at, request
import attendance_service as service
import attendance_clock as clock
import monthly_shift
import weekend_duty
import weekend_duty_management as management
import weekend_night_duty as night
from routers.schedule import get_my_employee_shift, _resolve_employee_shift_rows


@pytest.mark.parametrize('day', ['2026-11-07', '2026-11-08'])
@pytest.mark.parametrize('regular', ['early', 'customer_remote', None])
def test_published_duty_has_own_hours(environment, monkeypatch, day, regular):
    db, users = environment
    admin, person, other = users
    setup(db, users)
    monkeypatch.setattr('notification_ws.broadcast_to_users', lambda *args: None)
    if regular:
        monthly_shift.save_plan(db, admin, '2026-11', payload(person, shift=regular))
    saved = weekend_duty.save_plan(db, admin, '2026-11', weekend_duty.DutyWrite(
        revision=0, assignments=[{'user_id': person.id, 'department': 'customer', 'date': day}]))
    assert service.shift_for(db, person, date.fromisoformat(day)) is None
    assert get_my_employee_shift(date.fromisoformat(day), False, db, person)['me']['days'][0]['shift_code'] == 'off'
    management.publish(db, admin, '2026-11', SimpleNamespace(
        revision=saved['revision'], publication_revision=0, fixed_revision=0))
    shift = service.shift_for(db, person, date.fromisoformat(day))
    assert shift['label'] == '周末值班'
    assert shift['periods'] == ['09:30–12:00', '13:30–18:00']
    header = get_my_employee_shift(date.fromisoformat(day), False, db, person)['me']['days'][0]
    assert header['shift_code'] == 'weekend_duty'
    assert header['shift_label'] == shift['label']
    assert (header['start_time'], header['end_time']) == ('09:30', '18:00')
    assert header['periods'] == shift['periods']
    matrix = _resolve_employee_shift_rows(db, users, date(2026, 11, 6), date(2026, 11, 8))
    mine = next(row for row in matrix if row['user_id'] == str(person.id))
    assert next(row for row in mine['days'] if row['date'] == day)['shift_code'] == 'weekend_duty'
    assert next(row for row in mine['days'] if row['date'] != day and row['date'] != '2026-11-06')['shift_code'] == 'off'
    assert len(clock.segments(shift)) == 1
    assert service.shift_for(db, other, date.fromisoformat(day)) is None
    weekday = service.shift_for(db, person, date(2026, 11, 6))
    assert (weekday['code'] if weekday else None) == regular
    preview = service.preview_leave(db, person, service.LeaveWindow(
        start_at=at(f'{day}T09:00'), end_at=at(f'{day}T18:30')))
    assert preview['minutes'] == 420
    assert night.decorate(shift, {'mode': 'continuation'})['periods'] == [
        '09:30–12:00', '13:30–18:00', '19:00–23:00']
    monkeypatch.setattr(clock, 'now', lambda: at(f'{day}T09:30'))
    status = clock.today_status(db, person)
    assert status['shift']['code'] == 'weekend_duty'
    record = clock.check_in(db, person, request(), clock.CheckInWrite(
        breakfast_notice_accepted=True))['record']
    assert record['late_minutes'] == 0
    monkeypatch.setattr(clock, 'now', lambda: at(f'{day}T18:00'))
    finished = clock.check_out(db, person, request(), clock.CheckOutWrite(
        record_id=record['id'], early_work_confirmed=False,
        breakfast_after_eating=True, dinner_eaten=False))['record']
    assert finished['overtime_minutes'] == 0


@pytest.mark.parametrize('start,late', [('09:30', 0), ('09:45', 0), ('09:46', 1)])
def test_duty_retains_existing_lateness_grace(start, late):
    row = SimpleNamespace(day=date(2026, 11, 7), check_in=at(f'2026-11-07T{start}'),
                          check_out=at('2026-11-07T18:30'),
                          shift_snapshot={'periods': ['09:30–12:00', '13:30–18:00']})
    result = service.metrics(row)
    assert result['late_minutes'] == late
    if start == '09:30':
        assert result['overtime_minutes'] == 30


def test_workbench_shift_reads_published_weekday_and_fixed_shifts(environment, monkeypatch):
    import fixed_shift
    db, users = environment
    admin, person, other = users
    setup(db, users)
    monkeypatch.setattr('notification_ws.broadcast_to_users', lambda *args: None)
    # 1. 新版月/周排班安排早班后，工作台顶部接口应直接返回早班，而非未安排
    monthly_shift.save_plan(db, admin, '2026-11', payload(person, shift='early'))
    weekday = date(2026, 11, 25)
    header = get_my_employee_shift(weekday, False, db, person)['me']['days'][0]
    assert header['shift_code'] == 'early'
    assert header['shift_label'] == '早班'
    assert (header['start_time'], header['end_time']) == ('09:00', '18:30')
    assert header['periods'] == ['09:00–12:00', '13:30–18:30']
    assert header['source'] == 'published_schedule'

    # 2. 未排班的其他员工仍显示未安排，周末显示休息
    other_header = get_my_employee_shift(weekday, False, db, other)['me']['days'][0]
    assert other_header['shift_code'] == 'unassigned'
    assert get_my_employee_shift(date(2026, 11, 28), False, db, person)['me']['days'][0]['shift_code'] == 'off'

    # 3. 固定灵活班次（periods 为空）不报错且正确标记 fixed
    fixed_shift.save_config(db, admin, fixed_shift.FixedWrite(
        revision=0, assignments=[{'user_id': other.id, 'department': 'it', 'shift': 'flexible'}]))
    flex = get_my_employee_shift(weekday, False, db, other)['me']['days'][0]
    assert flex['shift_code'] == 'flexible'
    assert flex['shift_label'] == '灵活班次'
    assert (flex['start_time'], flex['end_time']) == (None, None)
    assert flex['periods'] == []
    assert flex['fixed'] is True
