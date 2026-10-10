"""进度业务时间：旧项目进度保存香港本地时间，新客户进度保存实际时刻。"""

from datetime import datetime, timedelta, timezone

BUSINESS_TIMEZONE = timezone(timedelta(hours=8))


def business_now():
    return datetime.now(BUSINESS_TIMEZONE)


def business_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=BUSINESS_TIMEZONE)
    return value.astimezone(BUSINESS_TIMEZONE)


def project_progress_datetime(value):
    """既有节点时间由本地业务表单录入，继续保存香港本地时间。"""
    return business_datetime(value).replace(tzinfo=None)
