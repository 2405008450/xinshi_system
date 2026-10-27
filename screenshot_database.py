"""截图授权不能与尚未释放连接的业务响应竞争同一个连接池。"""
from functools import lru_cache
from threading import Lock

from sqlalchemy import create_engine

from database import engine_options
from performance_monitoring import install_sqlalchemy_performance_hooks


_engine_lock = Lock()


def screenshot_engine(source):
    # 首批并发请求也只创建一个授权引擎。
    with _engine_lock:
        return _create_screenshot_engine(source)


@lru_cache(maxsize=4)
def _create_screenshot_engine(source):
    # 内存 SQLite 只用于隔离测试，另开引擎会指向另一份数据库。
    if source.dialect.name == 'sqlite' and source.url.database in (None, '', ':memory:'):
        return source
    options = dict(engine_options) if source.dialect.name == 'postgresql' else {'pool_pre_ping': True}
    options.update(pool_size=2, max_overflow=2, pool_timeout=10)
    if source.dialect.name == 'sqlite':
        options['connect_args'] = {'check_same_thread': False}
    auxiliary = create_engine(source.url, **options)
    install_sqlalchemy_performance_hooks(auxiliary)
    return auxiliary
