"""将明确的数据库连接容量不足转换为可重试的服务繁忙响应。"""
from sqlalchemy.exc import OperationalError,TimeoutError as PoolTimeoutError
from starlette.responses import JSONResponse


def capacity_response(error):
    busy=isinstance(error,PoolTimeoutError)
    if isinstance(error,OperationalError):
        original=error.orig
        message=str(original).lower()
        busy=getattr(original,'pgcode',None)=='53300' or 'too many clients already' in message or 'remaining connection slots are reserved' in message
    if not busy:return None
    return JSONResponse(status_code=503,content={'detail':'数据库连接繁忙，当前连接名额已满，请稍后点击刷新重试。'},headers={'Retry-After':'2'})
