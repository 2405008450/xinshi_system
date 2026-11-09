"""每个后端进程的连接预算与可识别、可回收的 PostgreSQL 空闲连接。"""
import os
import socket
from sqlalchemy import event


def integer_setting(name, default, minimum=0, maximum=10000000):
    value=int(os.getenv(name,str(default)))
    if not minimum<=value<=maximum:raise ValueError(f'{name} 必须在 {minimum} 至 {maximum} 之间')
    return value


def application_name(role):
    return f'xinshi/{socket.gethostname()}/{os.getpid()}/{role}'[:63]


def pool_options(role='business'):
    auxiliary=role=='screenshots'
    prefix='SCREENSHOT_DB_' if auxiliary else 'DB_'
    return {
        'pool_size':integer_setting(prefix+'POOL_SIZE',1 if auxiliary else 4,1,32),
        'max_overflow':integer_setting(prefix+'MAX_OVERFLOW',0,0,16),
        'pool_timeout':integer_setting('DB_POOL_TIMEOUT_SECONDS',10,1,120),
        'pool_recycle':integer_setting('DB_POOL_RECYCLE_SECONDS',300,1,86400),
        'pool_use_lifo':True,
    }


def install_idle_session_timeout(engine):
    if engine.dialect.name!='postgresql':return
    timeout=integer_setting('DB_IDLE_SESSION_TIMEOUT_MS',120000,0,86400000)
    @event.listens_for(engine,'connect')
    def configure(connection,record):
        # 旧版 PostgreSQL 不认识该配置；不能因此导致连接失败。
        if getattr(connection,'server_version',0)<140000 or not timeout:return
        previous=connection.autocommit
        connection.autocommit=True
        cursor=None
        try:
            cursor=connection.cursor()
            cursor.execute('SET idle_session_timeout = %s',(timeout,))
        finally:
            if cursor is not None:cursor.close()
            connection.autocommit=previous
