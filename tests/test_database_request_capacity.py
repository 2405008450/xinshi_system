import anyio
import pytest

from database_request_capacity import DatabaseRequestCapacityMiddleware


def test_concurrent_requests_are_bounded_through_response_cleanup():
    async def check():
        active = 0
        peak = 0
        completed = []
        async def endpoint(scope, receive, send):
            nonlocal active, peak
            active += 1
            peak = max(active, peak)
            await anyio.sleep(.01)
            await send({'type':'http.response.start','status':200,'headers':[]})
            await anyio.sleep(.01)  # 响应体和依赖收尾仍占用业务连接。
            await send({'type':'http.response.body','body':b'ok'})
            active -= 1
            completed.append(scope['index'])
        middleware = DatabaseRequestCapacityMiddleware(endpoint, limit=2)
        async def invoke(index):
            async def receive(): return {'type':'http.request','body':b''}
            async def send(message): pass
            await middleware({'type':'http','index':index}, receive, send)
        async with anyio.create_task_group() as tasks:
            for index in range(8): tasks.start_soon(invoke,index)
        assert peak == 2 and len(completed) == 8
    anyio.run(check)


def test_websockets_do_not_hold_http_capacity_and_errors_release_it():
    async def check():
        called = []
        async def endpoint(scope, *args):
            called.append(scope['type'])
            if scope.get('fail'): raise RuntimeError('isolated failure')
        middleware = DatabaseRequestCapacityMiddleware(endpoint, limit=1)
        async def unused(*args): pass
        with pytest.raises(RuntimeError):
            await middleware({'type':'http','fail':True}, unused, unused)
        await middleware({'type':'http'}, unused, unused)
        async with middleware.capacity:
            await middleware({'type':'websocket'}, unused, unused)
        assert called == ['http','http','websocket']
    anyio.run(check)
