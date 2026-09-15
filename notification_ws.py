import asyncio
from collections import defaultdict
from collections.abc import Iterable
from typing import Dict, Set
from uuid import UUID

from fastapi import WebSocket


_main_event_loop: asyncio.AbstractEventLoop | None = None


class NotificationConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: UUID, websocket: WebSocket) -> None:
        global _main_event_loop
        _main_event_loop = asyncio.get_running_loop()
        await websocket.accept()
        self.active_connections[str(user_id)].add(websocket)

    def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        user_connections = self.active_connections.get(str(user_id))
        if not user_connections:
            return
        user_connections.discard(websocket)
        if not user_connections:
            self.active_connections.pop(str(user_id), None)

    async def send_personal_message(self, user_id: UUID, payload: dict) -> None:
        stale_connections = []
        for websocket in list(self.active_connections.get(str(user_id), set())):
            try:
                await websocket.send_json(payload)
            except Exception:
                stale_connections.append(websocket)
        for websocket in stale_connections:
            self.disconnect(user_id, websocket)

    async def broadcast_to_users(self, user_ids: Iterable[UUID], payload: dict) -> None:
        for user_id in dict.fromkeys(user_ids):
            await self.send_personal_message(user_id, payload)


notification_manager = NotificationConnectionManager()


def _dispatch_on_main_loop(coroutine_factory) -> None:
    """把线程池中的同步端点消息安全派发回 WebSocket 所属事件循环。"""
    loop = _main_event_loop
    if loop is None or loop.is_closed():
        return

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    coroutine = coroutine_factory()
    if running_loop is loop:
        loop.create_task(coroutine)
    else:
        asyncio.run_coroutine_threadsafe(coroutine, loop)


def dispatch_personal_message(user_id: UUID, payload: dict) -> None:
    _dispatch_on_main_loop(lambda: notification_manager.send_personal_message(user_id, payload))


def broadcast_to_users(user_ids: Iterable[UUID], payload: dict) -> None:
    recipients = tuple(dict.fromkeys(user_ids))
    if not recipients:
        return
    _dispatch_on_main_loop(lambda: notification_manager.broadcast_to_users(recipients, payload))
