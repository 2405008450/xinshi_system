"""聊天候选人的排班状态；只读，不公开考勤或请假明细。"""
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import inspect
from models import EmployeeLeave
from chat_time import now, BUSINESS_TIMEZONE
from attendance_service import shifts_for, intervals
from work_report_calendar import is_workday


def work_presence(db, users, moment=None):
    if not users:
        return {}
    moment = (moment or now()).astimezone(BUSINESS_TIMEZONE)
    today = moment.date()
    # employee_leave 是请假管理的有效记录；考勤快照可能在记录删除后仍保留，不能据此判断当前请假。
    leave_ids=set()
    if inspect(db.connection()).has_table(EmployeeLeave.__tablename__):
        local_moment=moment.replace(tzinfo=None)  # 此表既有无时区字段按 UTC+8 存储。
        leave_ids={str(uid) for uid, in db.query(EmployeeLeave.employee_id).filter(
            EmployeeLeave.employee_id.in_([user.id for user in users]),
            EmployeeLeave.start_date<=local_moment,EmployeeLeave.end_date>local_moment).distinct()}

    try:
        current = shifts_for(db, users, today)
        previous = shifts_for(db, users, today - timedelta(days=1))
        workday = is_workday(today)
    except HTTPException as error:
        if error.status_code != 422:
            raise
        return {str(user.id): dict(work_state='on_leave' if str(user.id) in leave_ids else 'unknown', working_now=False if str(user.id) in leave_ids else None) for user in users}
    result = {}
    for user in users:
        uid = str(user.id)
        shift = current.get(uid)
        if uid in leave_ids:
            result[uid]=dict(work_state='on_leave',working_now=False)
            continue
        # 前一日跨午夜的班次仍属于工作时间，不能在零点误判为加班。
        windows = intervals(today, shift) + intervals(today - timedelta(days=1), previous.get(uid))
        working = any(left <= moment < right for left, right in windows)
        if shift and shift.get('flexible'):
            result[uid]=dict(work_state='flexible',working_now=None,shift_label=shift['label'],shift_periods=[])
            continue
        if working:
            state = 'working'
        elif shift or not workday:
            state = 'off_hours'
        else:
            state = 'unscheduled'
        effective = shift or (previous.get(uid) if working else None)
        result[uid] = dict(work_state=state, working_now=working if state != 'unscheduled' else None,
                           shift_label=effective['label'] if effective else None,
                           shift_periods=effective['periods'] if effective else [])
    return result
