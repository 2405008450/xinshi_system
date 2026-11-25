"""在进入同步依赖之前限制请求并发，避免等待连接的依赖占满工作线程。"""
import anyio
import re
import os
import json
from contextlib import AsyncExitStack
from time import perf_counter

from database import engine_options
from performance_monitoring import current_metrics


class DatabaseRequestCapacityMiddleware:
    message_create_path = re.compile(
        r'/(?:chat/(?:direct|discussions)|project-chat(?:/annotation)?)/[^/]+/messages'
    )

    def __init__(self, app, limit=None, transfer_limit=0, queue_timeout=None,
                 chat_send_reserve=0, chat_catalog_limit=0):
        self.app = app
        if limit is None:
            size = int(engine_options.get('pool_size', 5))
            overflow = int(engine_options.get('max_overflow', 5))
            # 给 WebSocket 鉴权及后台任务留出连接；截图授权使用独立连接池。
            reserve = min(2,max(1,size//3))
            limit = max(1, size + max(0, overflow) - reserve)
        # 使用预留连接中的一个名额，避免业务列表把登录和会话校验饿死。
        self.auth_capacity = anyio.CapacityLimiter(1)
        self.queue_timeout = float(queue_timeout if queue_timeout is not None else os.getenv('DB_REQUEST_QUEUE_TIMEOUT_SECONDS', '5'))
        # 文件请求单独使用预算内的少量名额，慢下载不能占满普通列表额度。
        transfer_limit = min(transfer_limit, max(0, limit - 1))
        self.capacity = anyio.CapacityLimiter(limit - transfer_limit)
        self.transfer_capacity = anyio.CapacityLimiter(transfer_limit) if transfer_limit else self.capacity
        ordinary_limit = limit - transfer_limit
        reserve = min(chat_send_reserve, max(0, ordinary_limit - 1))
        self.non_send_capacity = anyio.CapacityLimiter(ordinary_limit - reserve) if reserve else None
        self.catalog_capacity = anyio.CapacityLimiter(min(chat_catalog_limit, ordinary_limit - reserve)) if chat_catalog_limit else None

    @staticmethod
    def is_transfer(scope):
        path = scope.get('path', '')
        return path == '/project-files/source-path/inspect' or bool(re.search(
            r'/(?:files|attachments|images|material-uploads)(?:/[^/]+)?$|'
            r'/versions/[^/]+/download$|/office/sessions/[^/]+/source$|^/editor-screenshots(?:/[^/]+)?$', path))

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('path') == '/':
            return await self.app(scope, receive, send)
        started = perf_counter()
        auth_paths = {'/auth/session', '/auth/login', '/auth/login/json', '/auth/captcha', '/auth/captcha/required'}
        path = scope.get('path', '').rstrip('/')
        method = scope.get('method')
        is_catalog = method == 'GET' and path in {'/chat/sessions', '/chat/sessions/history'}
        is_send = method == 'POST' and self.message_create_path.fullmatch(path)
        if path in auth_paths:
            capacities = [self.auth_capacity]
        elif self.is_transfer(scope):
            capacities = [self.transfer_capacity]
        else:
            capacities = []
            if self.non_send_capacity and not is_send:
                capacities.append(self.non_send_capacity)
            capacities.append(self.capacity)

        async with AsyncExitStack() as acquired:
            if is_catalog and self.catalog_capacity:
                try:
                    self.catalog_capacity.acquire_nowait()
                except anyio.WouldBlock:
                    return await self.reject(send, 429, b'3', '会话目录繁忙，请稍后刷新')
                acquired.callback(self.catalog_capacity.release)
            with anyio.move_on_after(self.queue_timeout) as waiting:
                for capacity in capacities:
                    await acquired.enter_async_context(capacity)
            if waiting.cancel_called:
                return await self.reject(send, 503, b'1', '服务繁忙，请稍后重试')
            # 响应体发送和依赖清理结束后才归还名额。
            metrics = current_metrics()
            if metrics is not None:
                metrics.capacity_wait_ms += (perf_counter() - started) * 1000
            await self.app(scope, receive, send)

    @staticmethod
    async def reject(send, status, retry_after, detail):
        body = json.dumps({'detail': detail}, ensure_ascii=False).encode('utf-8')
        await send({'type': 'http.response.start', 'status': status, 'headers': [
            (b'content-type', b'application/json; charset=utf-8'), (b'retry-after', retry_after)]})
        await send({'type': 'http.response.body', 'body': body})
