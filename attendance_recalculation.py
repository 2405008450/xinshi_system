"""按已生效班次生成只读核算副本，原始打卡及申请快照始终保留。"""
from contextvars import ContextVar
from collections import defaultdict
from datetime import timedelta
from functools import wraps
from types import SimpleNamespace

from sqlalchemy.orm import object_session

_context = ContextVar('attendance_calculation', default=None)


class ScheduleInputs:
    """一次核算批量读取涉及的周/月安排，复用原班次解析规则。"""
    def __init__(self, db):
        self.db = db
        self.rows = {}
        self.availability = {}
        self.fixed_people = {}

    def ready(self, checker):
        if checker not in self.availability:
            self.availability[checker] = checker(self.db)
        return self.availability[checker]

    def get(self, model, key):
        if (model, key) not in self.rows:
            self.rows[model, key] = self.db.get(model, key)
        return self.rows[model, key]

    def prefetch(self, days):
        from monthly_shift import MonthlyShiftPlan, ready as monthly_ready
        from weekly_shift_publication import WeeklyShiftPublication, ready as weekly_ready
        from weekend_duty_management import WeekendDutyPublication, ready as duty_ready
        from weekend_night_duty import NightDutyPlan, ready as night_ready
        months = {day.replace(day=1) for day in days}
        weeks = {day - timedelta(days=day.weekday()) for day in days}
        for model, keys, checker in ((MonthlyShiftPlan, months, monthly_ready),
                                     (WeeklyShiftPublication, weeks, weekly_ready),
                                     (WeekendDutyPublication, months, duty_ready),
                                     (NightDutyPlan, months, night_ready)):
            missing = {key for key in keys if (model, key) not in self.rows}
            if not missing:
                continue
            column = list(model.__table__.primary_key.columns)[0]
            rows = self.db.query(model).filter(column.in_(missing)).all() if self.ready(checker) else []
            for key in missing:
                self.rows[model, key] = None
            for row in rows:
                self.rows[model, getattr(row, column.name)] = row

    def fixed_entries(self, values, only_active):
        import json
        from fixed_shift import entries
        key = json.dumps(values, sort_keys=True), only_active
        if key not in self.fixed_people:
            self.fixed_people[key] = entries(self.db, values, only_active=only_active)
        return self.fixed_people[key]


def calculation_scope(function):
    """一次业务调用共享班次查询；调用结束即清理，不跨请求缓存。"""
    @wraps(function)
    def wrapped(db, *args, **kwargs):
        current = _context.get()
        if current is not None and current['db'] is db:
            return function(db, *args, **kwargs)
        token = _context.set({'db': db, 'shifts': {}, 'groups': {}})
        try:
            return function(db, *args, **kwargs)
        finally:
            _context.reset(token)
    return wrapped


def state(db):
    current = _context.get()
    return current if current is not None and current['db'] is db else {'db': db, 'shifts': {}, 'groups': {}}


def load_shifts(db, pairs, cache):
    """同日人员一起解析，报表及后续年假、追责计算复用结果。"""
    from models import AppUser
    import attendance_service as attendance
    pending = set(pairs) - cache['shifts'].keys()
    if not pending:
        return
    users = {row.id: row for row in db.query(AppUser).filter(AppUser.id.in_({uid for uid, _ in pending})).all()}
    schedule = cache.setdefault('schedule', ScheduleInputs(db))
    schedule.prefetch({day for _, day in pending})
    by_day = defaultdict(list)
    for uid, day in pending:
        by_day[day].append(uid)
    for day, ids in sorted(by_day.items()):
        shifts = attendance.shifts_for(db, [users[uid] for uid in ids if uid in users], day, schedule=schedule)
        for uid in ids:
            cache['shifts'][uid, day] = shifts.get(str(uid))


def project_rows(db, rows):
    """输入须包含所选日期的全部组；返回普通对象，绝不污染 ORM。"""
    cache = state(db)
    load_shifts(db, {(row.user_id, row.day) for row in rows}, cache)
    groups = defaultdict(list)
    for row in rows:
        if hasattr(row, 'segment'):
            groups[row.user_id, row.day].append(row)
    cache['groups'].update(groups)
    return [project(row, db, cache) for row in rows]


def project(row, db=None, cache=None):
    if getattr(row, '_attendance_projected', False):
        return row
    db = db if db is not None else object_session(row) if hasattr(row, '_sa_instance_state') else None
    if db is None or not all(hasattr(row, name) for name in ('id', 'user_id', 'check_in', 'check_out')):
        return row
    import attendance_clock as clock
    import attendance_service as attendance
    cache = cache if cache is not None else state(db)
    key = row.user_id, row.day
    original = dict(row.shift_snapshot)
    values = {name: getattr(row, name) for name in ('id', 'user_id', 'day', 'check_in', 'check_out')}
    if hasattr(row, 'segment'):
        values.update(segment=row.segment, confirmations=dict(row.confirmations))
    if original.get('overtime_only'):
        shift = original
    else:
        load_shifts(db, {key}, cache)
        effective = cache['shifts'][key]
        if not effective:
            shift = {**original, 'recalculation_warning': '缺少有效班次依据，暂按原打卡班次核算，请联系行政核对'}
        else:
            effective = clock.clock_shift(effective)
            # 保留本人实际居家声明和跨日签退带入的上班基准，不带入旧班次时间。
            for name in ('late_start_at', 'start_adjustment_id', 'home_office_day', 'home_office_approval_status', 'home_office_hours', 'clock_pairs_unrestricted'):
                if name in original and (name != 'home_office_day' or original[name]):
                    effective[name] = original[name]
            if not hasattr(row, 'segment'):
                shift = effective
            else:
                if key not in cache['groups']:
                    cache['groups'][key] = db.query(clock.Clock).filter_by(user_id=row.user_id, day=row.day).all()
                siblings = cache['groups'][key]
                if not any(item.id == row.id for item in siblings):
                    siblings.append(row)
                regular = sorted([item for item in siblings if not item.shift_snapshot.get('overtime_only')], key=lambda item: (attendance.stamp(item.check_in), item.segment))
                position = next((index for index, item in enumerate(regular) if item.id == row.id), 0)
                parts = clock.segments(effective)
                if clock.allows_multiple(effective):
                    shift = clock.snapshot(effective, row.segment)
                    shift['continuation'] = position > 0
                elif original.get('code') == effective.get('code') and row.segment < len(parts):
                    # 漏了第一段的历史补卡仍按其原段号核算，不能误映射为白天。
                    shift = clock.snapshot(effective, row.segment)
                elif position < len(parts):
                    shift = clock.snapshot(effective, position)
                else:
                    # 改为单段后多出来的实际工作组仍保留，只对第一组判断迟到。
                    shift = {**clock.snapshot(effective, 0), 'continuation': True,
                             'recalculation_warning': '已有打卡组数超过新班次分段数，保留实际工作组，请行政核对'}
                if len(parts) > 1 and not clock.allows_multiple(effective) and len(clock.segments(clock.clock_shift(original))) == 1:
                    shift = {**shift, 'periods': effective['periods'], 'continuation': position > 0,
                             'recalculation_warning': '原打卡为整日组，新班次为分段班，暂按完整班次核算，请行政核对分段'}
                # 晚餐只抵扣一次，依据实际确认顺序，不沿用可能失效的旧组标记。
                preceding = [item for item in siblings if item.id != row.id and item.check_out and
                             (attendance.stamp(item.check_out), item.segment) <
                             (attendance.stamp(row.check_out) if row.check_out else attendance.stamp(row.check_in), row.segment)]
                shift['dinner_already_deducted'] = any(item.confirmations.get('dinner_eaten') is True and clock.dinner_confirmation_required(item.day, item.check_out) for item in preceding)
    return SimpleNamespace(**values, shift_snapshot=shift, _attendance_projected=True)


def leave_days(db, leave, saved_days=None):
    """申请实际区间不变；每个业务日按生效班次重新求交。"""
    import attendance_service as attendance
    cache = state(db)
    uid = getattr(leave, 'employee_id', None) or leave.user_id
    left = attendance.stamp(getattr(leave, 'start_date', None) or leave.start_at)
    right = attendance.stamp(getattr(leave, 'end_date', None) or leave.end_at)
    day = left.date()
    days = []
    while attendance.midnight(day) < right:
        days.append(day)
        day += timedelta(days=1)
    load_shifts(db, {(uid, day) for day in days}, cache)
    saved = {item['day']: item for item in saved_days or []}
    result = []
    for day in days:
        shift = cache['shifts'][uid, day]
        if shift is None and day.isoformat() in saved:
            old = saved[day.isoformat()]
            result.append({**old, 'shift': {**(old.get('shift') or {}), 'recalculation_warning': '缺少有效班次依据，暂按原请假快照核算'}})
            continue
        old = saved.get(day.isoformat())
        if old and shift and all((old.get('shift') or {}).get(name) == shift.get(name) for name in ('code', 'periods')):
            # 班次未变时保留既有核准时长；只重算受班次调整影响的日期。
            result.append({**old, 'shift': shift})
            continue
        minutes = round(sum(attendance.overlap(left, right, a, b) for a, b in attendance.intervals(day, shift)) / 60, 2)
        result.append({'day': day.isoformat(), 'shift': shift, 'minutes': minutes})
    return result


def prime_leaves(db, leaves):
    """先收集全部申请日期，避免不同人员的同日请假逐条查询。"""
    import attendance_service as attendance
    pairs = set()
    for leave in leaves:
        uid = getattr(leave, 'employee_id', None) or leave.user_id
        left = attendance.stamp(getattr(leave, 'start_date', None) or leave.start_at)
        right = attendance.stamp(getattr(leave, 'end_date', None) or leave.end_at)
        day = left.date()
        while attendance.midnight(day) < right:
            pairs.add((uid, day))
            day += timedelta(days=1)
    load_shifts(db, pairs, state(db))


def publish_change(db):
    """由班次写入方提交成功后调用；广播只用于界面失效通知。"""
    from models import AppUser
    from notification_ws import broadcast_to_users
    recipients = [str(uid) for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True), AppUser.is_deleted.is_(False)).all()]
    broadcast_to_users(recipients, {'type': 'attendance_schedule_changed'})
