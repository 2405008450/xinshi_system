"""只使用伪 PostgreSQL 连接及临时 SQLite，不连接共享数据库。"""
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.exc import TimeoutError
from sqlalchemy.pool import QueuePool
import database_pool_policy as policy


def test_pool_budget_is_bounded_and_separate_for_business_and_grants(monkeypatch):
    for key in ['DB_POOL_SIZE','DB_MAX_OVERFLOW','DB_POOL_RECYCLE_SECONDS','DB_POOL_TIMEOUT_SECONDS','SCREENSHOT_DB_POOL_SIZE','SCREENSHOT_DB_MAX_OVERFLOW']:monkeypatch.delenv(key,raising=False)
    assert policy.pool_options()['pool_size']==4 and policy.pool_options()['max_overflow']==0
    assert policy.pool_options('screenshots')['pool_size']==1 and policy.pool_options('screenshots')['max_overflow']==0
    assert policy.pool_options()['pool_use_lifo'] is True
    monkeypatch.setenv('DB_POOL_SIZE','0')
    with pytest.raises(ValueError):policy.pool_options()
    monkeypatch.setenv('DB_POOL_SIZE','4');monkeypatch.setenv('DB_MAX_OVERFLOW','-1')
    with pytest.raises(ValueError):policy.pool_options()


def listener(monkeypatch,timeout='120000'):
    monkeypatch.setenv('DB_IDLE_SESSION_TIMEOUT_MS',timeout)
    callbacks=[]
    monkeypatch.setattr(policy.event,'listens_for',lambda *args,**kwargs:lambda fn:(callbacks.append(fn) or fn))
    policy.install_idle_session_timeout(SimpleNamespace(dialect=SimpleNamespace(name='postgresql')))
    return callbacks[0]


def test_idle_timeout_is_only_set_on_own_pg14plus_sessions_and_outside_transactions(monkeypatch):
    callback=listener(monkeypatch)
    connection=SimpleNamespace(server_version=180006,autocommit=False)
    calls=[]
    class Cursor:
        def execute(self,sql,params):
            assert connection.autocommit is True
            calls.append((sql,params))
        def close(self):calls.append('closed')
    connection.cursor=lambda:Cursor()
    callback(connection,None)
    assert calls==[('SET idle_session_timeout = %s',(120000,)),'closed']
    assert connection.autocommit is False
    calls.clear();connection.server_version=130000;callback(connection,None)
    assert not calls


def test_timeout_configuration_failure_restores_driver_state(monkeypatch):
    callback=listener(monkeypatch)
    closed=[]
    class Cursor:
        def execute(self,*args):raise RuntimeError('connection lost')
        def close(self):closed.append(True)
    connection=SimpleNamespace(server_version=180006,autocommit=False,cursor=lambda:Cursor())
    with pytest.raises(RuntimeError):callback(connection,None)
    assert connection.autocommit is False and closed==[True]


def test_capacity_middleware_keeps_three_requests_and_one_background_slot(monkeypatch):
    import database_request_capacity as middleware
    monkeypatch.setattr(middleware,'engine_options',{'pool_size':4,'max_overflow':0})
    wrapped=middleware.DatabaseRequestCapacityMiddleware(None)
    assert wrapped.capacity.total_tokens==3


def test_pool_overload_is_bounded_and_excess_request_does_not_leak_connections(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "capacity.db"}',poolclass=QueuePool,pool_size=2,max_overflow=0,pool_timeout=.05,pool_pre_ping=True)
    first=engine.connect();second=engine.connect()
    try:
        with pytest.raises(TimeoutError):engine.connect()
        assert engine.pool.checkedout()==2
        first.close()
        with engine.connect() as recovered:assert recovered.execute(text('SELECT 1')).scalar()==1
    finally:first.close();second.close()
    assert engine.pool.checkedout()==0
    engine.dispose()


def test_pre_ping_replaces_a_server_closed_idle_connection(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "idle.db"}',poolclass=QueuePool,pool_size=1,max_overflow=0,pool_pre_ping=True)
    with engine.connect() as connection:
        raw=connection.connection.driver_connection
        assert connection.execute(text('SELECT 1')).scalar()==1
    # 模拟数据库已关闭池中的空闲物理连接，不接触任何共享数据库。
    raw.close()
    with engine.connect() as recovered:
        assert recovered.connection.driver_connection is not raw
        assert recovered.execute(text('SELECT 1')).scalar()==1
    assert engine.pool.checkedout()==0
    engine.dispose()
