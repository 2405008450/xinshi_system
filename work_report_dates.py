"""工作报告日：UTC+8 每天 07:00 换日，显式选择的历史报告日期不重写。"""
from datetime import datetime,time,timedelta
from chat_time import now,BUSINESS_TIMEZONE


def report_business_date(value=None):
    value=value or now()
    local=value.replace(tzinfo=BUSINESS_TIMEZONE) if value.tzinfo is None else value.astimezone(BUSINESS_TIMEZONE)
    return (local-timedelta(hours=7)).date()


def report_day_range(day):
    start=datetime.combine(day,time(hour=7))
    return start,start+timedelta(days=1)
