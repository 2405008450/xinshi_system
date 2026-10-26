import asyncio
from collections import defaultdict
from collections.abc import Iterable
from typing import Dict, Set
from uuid import UUID
from time import monotonic
from threading import RLock
import re

from fastapi import WebSocket


_main_event_loop: asyncio.AbstractEventLoop | None = None


class NotificationConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.annotation_subscriptions = {}
        self.connection_presence = {}
        self.presence_lock = RLock()

    def touch(self, user_id, websocket):
        with self.presence_lock:
            key = (str(user_id), websocket)
            if key in self.connection_presence:
                kind, _ = self.connection_presence[key]
                self.connection_presence[key] = (kind, monotonic())

    def desktop_presence(self, user_ids):
        now = monotonic()
        with self.presence_lock:
            online = {uid for (uid, _), (kind, seen) in self.connection_presence.items()
                      if kind == 'desktop' and now - seen < 75}
        return {str(uid): str(uid) in online for uid in user_ids}

    def annotation_viewers(self, project_id):
        return {UUID(user_id) for (user_id, _), projects in list(self.annotation_subscriptions.items()) if project_id in projects}

    def watch_annotation(self, user_id, websocket, project_id, active):
        key = (str(user_id), websocket)
        projects = self.annotation_subscriptions.setdefault(key, set())
        if active:
            projects.add(str(project_id))
        else:
            projects.discard(str(project_id))

    async def connect(self, user_id: UUID, websocket: WebSocket, client_type: str = '') -> None:
        global _main_event_loop
        _main_event_loop = asyncio.get_running_loop()
        await websocket.accept()
        self.active_connections[str(user_id)].add(websocket)
        agent = getattr(websocket, 'headers', {}).get('user-agent', '')
        kind = client_type if client_type in ('desktop', 'mobile') else (
            'mobile' if re.search(r'Android|iPhone|iPad|iPod|Mobile', agent, re.I) else 'desktop' if agent else 'unknown')
        with self.presence_lock:
            self.connection_presence[(str(user_id), websocket)] = (kind, monotonic())

    def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        with self.presence_lock:
            self.connection_presence.pop((str(user_id), websocket), None)
        self.annotation_subscriptions.pop((str(user_id), websocket), None)
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
