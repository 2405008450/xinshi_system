"""仅使用内存数据库、临时文件及受控阻塞，不访问业务数据库或真实共享。"""
import asyncio
import logging
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import anyio
import pytest
from fastapi import HTTPException, Request
from sqlalchemy import create_engine, text

from bounded_file_io import BoundedFileIO
from database_request_capacity import DatabaseRequestCapacityMiddleware
import performance_monitoring as perf


def test_smb_timeout_retains_slot_until_real_completion():
    async def scenario():
        pool = BoundedFileIO(workers=1, timeout=.03)
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        def blocked():
            started.set()
            try:
                release.wait(2)
                raise OSError('network disconnected')
            finally:
                finished.set()
        try:
            with pytest.raises(HTTPException) as timeout:
                await pool.run(blocked)
            assert started.is_set() and timeout.value.status_code == 504
            with pytest.raises(HTTPException) as busy:
                await pool.run(lambda: 'must not run')
            assert busy.value.status_code == 503
            release.set()
            await asyncio.to_thread(finished.wait, 1)
            # 完成回调归还名额后可以恢复，不依赖超时请求仍然存在。
            await asyncio.sleep(.01)
            assert await pool.run(lambda: '恢复') == '恢复'
        finally:
            release.set()
            pool.executor.shutdown(wait=True)
    asyncio.run(scenario())


def test_smb_client_cancel_does_not_free_running_slot():
    async def scenario():
        pool = BoundedFileIO(workers=1, timeout=1)
        started, release = threading.Event(), threading.Event()
        def blocked():
            started.set()
            release.wait(2)
        try:
            task = asyncio.create_task(pool.run(blocked))
            assert await asyncio.to_thread(started.wait, 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            with pytest.raises(HTTPException) as busy:
                await pool.run(lambda: None)
            assert busy.value.status_code == 503
        finally:
            release.set()
            await asyncio.to_thread(pool.executor.shutdown, wait=True)
    asyncio.run(scenario())


@pytest.mark.parametrize('error', [PermissionError('denied'), FileNotFoundError('offline')])
def test_smb_failure_releases_worker(error):
    async def scenario():
        pool = BoundedFileIO(workers=1)
        def fail():
            raise error
        try:
            with pytest.raises(type(error)):
                await pool.run(fail)
            assert await pool.run(lambda: '中文目录') == '中文目录'
        finally:
            pool.executor.shutdown(wait=True)
    asyncio.run(scenario())


def test_shared_route_preserves_chinese_unc_and_maps_permission_failure(monkeypatch):
    from routers import project_files as routes
    from schemas import ProjectSourcePathInspectRequest
    seen = []
    def inspect(path):
        seen.append(path)
        if len(seen) == 2:
            raise ValueError('读取原文路径失败：权限不足')
        return {'storage_path': path, 'source_file_name': '中文原文.docx'}
    monkeypatch.setenv('OPENPATH_ALLOWED_ROOTS', r'\\Win-server\服务器资料7')
    monkeypatch.setattr(routes, 'inspect_project_source_path', inspect)
    payload = ProjectSourcePathInspectRequest(storage_path=r'\\Win-server\服务器资料7\客户\中文原文.docx')
    async def scenario():
        assert (await routes.inspect_source_path(payload))['storage_path'] == payload.storage_path
        with pytest.raises(HTTPException) as denied:
            await routes.inspect_source_path(payload)
        assert denied.value.status_code == 400 and '权限不足' in denied.value.detail
    asyncio.run(scenario())
    assert seen == [payload.storage_path, payload.storage_path]


def test_slow_transfer_cannot_consume_normal_request_budget():
    async def scenario():
        release, entered = anyio.Event(), anyio.Event()
        completed = []
        async def app(scope, receive, send):
            if scope['path'].endswith('/files/123'):
                entered.set()
                await release.wait()
            completed.append(scope['path'])
        middleware = DatabaseRequestCapacityMiddleware(app, limit=3, transfer_limit=1)
        async def unused(*args):
            pass
        async def invoke(path):
            await middleware({'type': 'http', 'path': path}, unused, unused)
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(invoke, '/chat/direct/id/files/123')
            await entered.wait()
            # 传输名额全部占满时，普通查询与无数据库探针仍可完成。
            with anyio.fail_after(.5):
                await invoke('/talents/page')
                async with middleware.capacity:
                    await invoke('/')
            assert completed == ['/talents/page', '/']
            release.set()
    anyio.run(scenario)


def test_pool_acquisition_and_sql_time_are_separate(caplog):
    engine = create_engine('sqlite://', poolclass=perf.ObservedQueuePool,
                           pool_size=1, max_overflow=0, connect_args={'check_same_thread': False})
    perf.install_sqlalchemy_performance_hooks(engine)
    held = engine.connect()
    metrics, token = perf.begin_request('isolated-pool')
    release = threading.Timer(.04, held.close)
    release.start()
    try:
        with engine.connect() as connection:
            assert connection.execute(text('SELECT 1')).scalar() == 1
        assert metrics.pool_acquire_ms >= 15
        assert metrics.sql_count == 1 and metrics.db_ms < metrics.pool_acquire_ms
        request = Request({'type': 'http', 'method': 'GET', 'path': '/probe', 'headers': [],
                           'query_string': b'token=must-not-log'})
        with caplog.at_level(logging.INFO, logger='xinshi.performance'):
            perf.LOG_ALL_REQUESTS, previous = True, perf.LOG_ALL_REQUESTS
            try:
                perf.finish_request_log(request, metrics, 200)
            finally:
                perf.LOG_ALL_REQUESTS = previous
        assert '+08:00' in caplog.text and 'pool_acquire_ms=' in caplog.text
        assert 'must-not-log' not in caplog.text
    finally:
        perf.end_request(token)
        release.join()
        held.close()
        engine.dispose()


def test_office_slow_database_does_not_block_other_coroutines(monkeypatch):
    from routers import annotation_office as routes
    async def scenario():
        started, release = threading.Event(), threading.Event()
        loop_thread = threading.get_ident()
        def owned(*args, **kwargs):
            assert threading.get_ident() != loop_thread
            started.set()
            assert release.wait(1), '同步数据库阻塞了事件循环'
            return SimpleNamespace(state='open', mode='view', lease_until=None)
        async def local(_):
            return None
        monkeypatch.setattr(routes, 'forward', local)
        monkeypatch.setattr(routes.office, 'owned_session', owned)
        monkeypatch.setattr(routes.office, 'describe', lambda *args: {'state': 'open'})
        db = SimpleNamespace(commit=lambda: None)
        task = asyncio.create_task(routes.heartbeat(uuid4(), None, db, SimpleNamespace(id=uuid4())))
        try:
            assert await asyncio.to_thread(started.wait, 1)
            release.set()
            assert await task == {'state': 'open'}
        finally:
            release.set()
            await task
    asyncio.run(scenario())


def test_loop_monitor_detects_blocking_and_stops():
    async def scenario():
        stop = asyncio.Event()
        task = asyncio.create_task(perf.monitor_event_loop(stop))
        await asyncio.sleep(.02)
        time.sleep(.14)  # 故意模拟遗留同步路由阻塞。
        await asyncio.sleep(.01)
        assert perf._loop_lag_ms > 30
        stop.set()
        await task
    asyncio.run(scenario())
