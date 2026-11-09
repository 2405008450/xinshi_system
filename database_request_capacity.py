"""在进入同步依赖之前限制请求并发，避免等待连接的依赖占满工作线程。"""
import anyio
import os
import json

from database import engine_options


class DatabaseRequestCapacityMiddleware:
    def __init__(self, app, limit=None, queue_timeout=None):
        self.app = app
        if limit is None:
            size = int(engine_options.get('pool_size', 5))
            overflow = int(engine_options.get('max_overflow', 5))
            # 给 WebSocket 鉴权及后台任务留出连接；截图授权使用独立连接池。
            reserve = min(2,max(1,size//3))
            limit = max(1, size + max(0, overflow) - reserve)
        self.capacity = anyio.CapacityLimiter(limit)
        self.queue_timeout = float(queue_timeout if queue_timeout is not None else os.getenv('DB_REQUEST_QUEUE_TIMEOUT_SECONDS', '5'))

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        # 等候名额也有上限，避免浏览器已超时的请求仍在队尾无限堆积。
        with anyio.move_on_after(self.queue_timeout) as waiting:
            await self.capacity.acquire()
        if waiting.cancel_called:
            body = json.dumps({'detail': '服务繁忙，请稍后重试'}, ensure_ascii=False).encode('utf-8')
            await send({'type': 'http.response.start', 'status': 503, 'headers': [
                (b'content-type', b'application/json; charset=utf-8'), (b'retry-after', b'1')]})
            await send({'type': 'http.response.body', 'body': body})
            return
        # 包含响应体发送和依赖清理，不能在端点返回时提前释放额度。
        try:
            await self.app(scope, receive, send)
        finally:
            self.capacity.release()
