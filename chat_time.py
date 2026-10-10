"""聊天旧无时区字段已按香港本地时间保存；新字段按实际时刻保存。"""
from datetime import datetime, timedelta, timezone

BUSINESS_TIMEZONE = timezone(timedelta(hours=8))


def now():
    return datetime.now(BUSINESS_TIMEZONE)


def api_time(value):
    if isinstance(value, datetime):
        return (value.replace(tzinfo=BUSINESS_TIMEZONE) if value.tzinfo is None else value.astimezone(BUSINESS_TIMEZONE))
    if isinstance(value, list):
        return [api_time(item) for item in value]
    if isinstance(value, dict):
        return {key: api_time(item) for key, item in value.items()}
    return value
