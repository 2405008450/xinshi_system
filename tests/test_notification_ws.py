import asyncio
from uuid import uuid4

import notification_ws


def test_thread_dispatch_reaches_socket_on_owner_loop():
    async def scenario():
        user_id = uuid4()
        received = []
        delivered = asyncio.Event()

        class FakeWebSocket:
            async def accept(self):
                return None

            async def send_json(self, payload):
                received.append(payload)
                delivered.set()

        websocket = FakeWebSocket()
        await notification_ws.notification_manager.connect(user_id, websocket)
        try:
            await asyncio.to_thread(
                notification_ws.dispatch_personal_message,
                user_id,
                {"type": "chat_message"},
            )
            await asyncio.wait_for(delivered.wait(), timeout=1)
        finally:
            notification_ws.notification_manager.disconnect(user_id, websocket)

        assert received == [{"type": "chat_message"}]

    asyncio.run(scenario())


def test_sync_dispatch_uses_websocket_main_loop(monkeypatch):
    scheduled = []

    class FakeLoop:
        @staticmethod
        def is_closed():
            return False

    def capture(coroutine, loop):
        scheduled.append(loop)
        coroutine.close()

    fake_loop = FakeLoop()
    monkeypatch.setattr(notification_ws, "_main_event_loop", fake_loop)
    monkeypatch.setattr(notification_ws.asyncio, "run_coroutine_threadsafe", capture)

    notification_ws.dispatch_personal_message(uuid4(), {"type": "notification"})

    assert scheduled == [fake_loop]


def test_broadcast_deduplicates_recipients_before_dispatch(monkeypatch):
    first = uuid4()
    second = uuid4()
    captured = []

    async def noop():
        return None

    def capture_broadcast(user_ids, payload):
        captured.append((tuple(user_ids), payload))
        return noop()

    monkeypatch.setattr(
        notification_ws,
        "_dispatch_on_main_loop",
        lambda coroutine_factory: coroutine_factory().close(),
    )
    monkeypatch.setattr(notification_ws.notification_manager, "broadcast_to_users", capture_broadcast)

    notification_ws.broadcast_to_users([first, first, second], {"type": "chat_message"})

    assert captured == [((first, second), {"type": "chat_message"})]
