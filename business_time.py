"""已确认采用 UTC+8 本地存储的业务时间工具，不用于推断历史 UTC 字段。"""
from datetime import datetime, timedelta, timezone

BUSINESS_TIMEZONE = timezone(timedelta(hours=8))


def business_now() -> datetime:
    """无时区数据库字段保存显式 UTC+8 的本地时间。"""
    return datetime.now(BUSINESS_TIMEZONE).replace(tzinfo=None)


def business_iso(value: datetime | None) -> str | None:
    """已确认的 UTC+8 无时区值补偏移，带时区值转换实际时刻。"""
    if value is None:
        return None
    moment = value.replace(tzinfo=BUSINESS_TIMEZONE) if value.tzinfo is None else value.astimezone(BUSINESS_TIMEZONE)
    return moment.isoformat()
