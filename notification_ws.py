import asyncio
from collections import defaultdict
from typing import Dict, Set
from uuid import UUID

from fastapi import WebSocket


class NotificationConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: UUID, websocket: WebSocket) -> None:
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


notification_manager = NotificationConnectionManager()



def dispatch_personal_message(user_id: UUID, payload: dict) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(notification_manager.send_personal_message(user_id, payload))
        return

    loop.create_task(notification_manager.send_personal_message(user_id, payload))
