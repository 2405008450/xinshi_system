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


@pytest.mark.parametrize('path', ['/notifications', '/project-chat/attachments/file-id'])
def test_queue_timeout_returns_retryable_error_without_running_endpoint(path):
    async def check():
        called=[];messages=[]
        async def endpoint(*args):called.append(True)
        async def unused(*args):pass
        async def send(message):messages.append(message)
        middleware=DatabaseRequestCapacityMiddleware(endpoint,limit=2,transfer_limit=1,queue_timeout=.02)
        async def blocked():await middleware({'type':'http','path':path},unused,send)
        capacity=middleware.transfer_capacity if middleware.is_transfer({'path':path}) else middleware.capacity
        async with capacity:
            async with anyio.create_task_group() as tasks:tasks.start_soon(blocked)
        assert not called
        assert messages[0]['status']==503
        assert (b'retry-after',b'1') in messages[0]['headers']
        await middleware({'type':'http','path':path},unused,send)
        assert called==[True]
    anyio.run(check)


def test_auth_can_run_when_business_capacity_is_full_and_remains_bounded():
    async def check():
        called = []
        messages = []
        async def endpoint(scope, *args): called.append(scope['path'])
        async def unused(*args): pass
        async def send(message): messages.append(message)
        middleware = DatabaseRequestCapacityMiddleware(endpoint, limit=1, queue_timeout=.01)
        async with middleware.capacity:
            await middleware({'type': 'http', 'path': '/auth/session'}, unused, send)
            await middleware({'type': 'http', 'path': '/auth/login/json'}, unused, send)
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(middleware, {'type': 'http', 'path': '/work-items/my'}, unused, send)
        assert called == ['/auth/session', '/auth/login/json']
        assert messages[0]['status'] == 503
        async with middleware.auth_capacity:
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(middleware, {'type': 'http', 'path': '/auth/session'}, unused, send)
        assert messages[-2]['status'] == 503
        assert middleware.auth_capacity.borrowed_tokens == 0
    anyio.run(check)


def test_catalog_surge_leaves_capacity_for_all_four_chat_send_routes():
    async def check():
        catalog_started = anyio.Event()
        all_sends_started = anyio.Event()
        release = anyio.Event()
        scopes = {
            'catalog': ('GET', '/chat/sessions/'),
            'history': ('GET', '/chat/sessions/history'),
            'business': ('GET', '/work-items/my'),
            'direct': ('POST', '/chat/direct/id/messages'),
            'discussion': ('POST', '/chat/discussions/id/messages'),
            'translation': ('POST', '/project-chat/id/messages'),
            'annotation': ('POST', '/project-chat/annotation/id/messages/'),
        }
        sends = {'direct', 'discussion', 'translation', 'annotation'}
        started_sends = set()
        results = {}

        async def endpoint(scope, receive, send):
            name = scope['name']
            if name == 'catalog':
                catalog_started.set()
            elif name in sends:
                started_sends.add(name)
                if started_sends == sends:
                    all_sends_started.set()
            await release.wait()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})

        async def invoke(name, index=0):
            method, path = scopes[name]

            async def send(message):
                if message['type'] == 'http.response.start':
                    results[name, index] = message

            await middleware({'type': 'http', 'name': name, 'method': method, 'path': path}, None, send)

        middleware = DatabaseRequestCapacityMiddleware(
            endpoint, limit=5, chat_send_reserve=4, chat_catalog_limit=1, queue_timeout=.05,
        )
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(invoke, 'catalog')
            await catalog_started.wait()
            for index in range(44):
                tasks.start_soon(invoke, 'history', index)
            tasks.start_soon(invoke, 'business')
            for name in sends:
                tasks.start_soon(invoke, name)
            with anyio.fail_after(1):
                await all_sends_started.wait()
                while len(results) < 45:
                    await anyio.sleep(.005)
            release.set()

        assert len(results) == 50
        assert all(results[name, 0]['status'] == 200 for name in sends | {'catalog'})
        assert results['business', 0]['status'] == 503
        assert all(results['history', index]['status'] == 429 for index in range(44))
        assert (b'retry-after', b'3') in results['history', 0]['headers']
        assert all(limiter.borrowed_tokens == 0 for limiter in [
            middleware.capacity, middleware.non_send_capacity, middleware.catalog_capacity,
        ])

    anyio.run(check)
