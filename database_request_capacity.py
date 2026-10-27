"""在进入同步依赖之前限制请求并发，避免等待连接的依赖占满工作线程。"""
import anyio

from database import engine_options


class DatabaseRequestCapacityMiddleware:
    def __init__(self, app, limit=None):
        self.app = app
        if limit is None:
            size = int(engine_options.get('pool_size', 5))
            overflow = int(engine_options.get('max_overflow', 5))
            # 给 WebSocket 鉴权及后台任务留出连接；截图授权使用独立连接池。
            limit = max(1, size + max(0, overflow) - 2)
        self.capacity = anyio.CapacityLimiter(limit)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        # 包含响应体发送和依赖清理，不能在端点返回时提前释放额度。
        async with self.capacity:
            await self.app(scope, receive, send)
