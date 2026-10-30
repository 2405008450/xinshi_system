"""聊天候选人的排班状态；只读，不公开考勤或请假明细。"""
from datetime import timedelta
from fastapi import HTTPException
from chat_time import now, BUSINESS_TIMEZONE
from attendance_service import shifts_for, intervals
from work_report_calendar import is_workday


def work_presence(db, users, moment=None):
    if not users:
        return {}
    moment = (moment or now()).astimezone(BUSINESS_TIMEZONE)
    today = moment.date()
    try:
        current = shifts_for(db, users, today)
        previous = shifts_for(db, users, today - timedelta(days=1))
        workday = is_workday(today)
    except HTTPException as error:
        if error.status_code != 422:
            raise
        return {str(user.id): dict(work_state='unknown', working_now=None) for user in users}
    result = {}
    for user in users:
        uid = str(user.id)
        shift = current.get(uid)
        # 前一日跨午夜的班次仍属于工作时间，不能在零点误判为加班。
        windows = intervals(today, shift) + intervals(today - timedelta(days=1), previous.get(uid))
        working = any(left <= moment < right for left, right in windows)
        if shift and shift.get('flexible'):
            result[uid]=dict(work_state='unknown',working_now=None,shift_label=shift['label'],shift_periods=[])
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
