"""在进入同步依赖之前限制请求并发，避免等待连接的依赖占满工作线程。"""
import anyio
import re
import os
import json
from time import perf_counter

from database import engine_options
from performance_monitoring import current_metrics


class DatabaseRequestCapacityMiddleware:
    def __init__(self, app, limit=None, transfer_limit=0, queue_timeout=None):
        self.app = app
        if limit is None:
            size = int(engine_options.get('pool_size', 5))
            overflow = int(engine_options.get('max_overflow', 5))
            # 给 WebSocket 鉴权及后台任务留出连接；截图授权使用独立连接池。
            limit = max(1, size + max(0, overflow) - 2)
        self.queue_timeout = float(queue_timeout if queue_timeout is not None else os.getenv('DB_REQUEST_QUEUE_TIMEOUT_SECONDS', '5'))
        # 文件请求单独使用预算内的少量名额，慢下载不能占满普通列表额度。
        transfer_limit = min(transfer_limit, max(0, limit - 1))
        self.capacity = anyio.CapacityLimiter(limit - transfer_limit)
        self.transfer_capacity = anyio.CapacityLimiter(transfer_limit) if transfer_limit else self.capacity

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
        capacity = self.transfer_capacity if self.is_transfer(scope) else self.capacity
        # 普通请求与文件请求分别排队，等候超时后返回可重试响应。
        with anyio.move_on_after(self.queue_timeout) as waiting:
            await capacity.acquire()
        if waiting.cancel_called:
            body = json.dumps({'detail': '服务繁忙，请稍后重试'}, ensure_ascii=False).encode('utf-8')
            await send({'type': 'http.response.start', 'status': 503, 'headers': [
                (b'content-type', b'application/json; charset=utf-8'), (b'retry-after', b'1')]})
            await send({'type': 'http.response.body', 'body': body})
            return
        # 包含响应体发送和依赖清理，不能在端点返回时提前释放额度。
        try:
            metrics = current_metrics()
            if metrics is not None:
                metrics.capacity_wait_ms += (perf_counter() - started) * 1000
            await self.app(scope, receive, send)
        finally:
            capacity.release()
