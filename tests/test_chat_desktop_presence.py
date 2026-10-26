"""电脑在线提示只使用内存连接和隔离数据库。"""
import asyncio
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment  # noqa: F401


class Socket:
    def __init__(self, agent=''):
        self.headers = {'user-agent': agent}
    async def accept(self):
        pass


def test_mobile_does_not_count_multiple_desktops_disconnect_and_expiry(monkeypatch):
    import notification_ws as ws
    now = [100.0]
    monkeypatch.setattr(ws, 'monotonic', lambda: now[0])
    manager = ws.NotificationConnectionManager()
    uid = uuid4()
    mobile, first, second = Socket('iPhone'), Socket('Windows'), Socket('Windows')
    async def scenario():
        await manager.connect(uid, mobile, 'mobile')
        assert manager.desktop_presence([uid])[str(uid)] is False
        await manager.connect(uid, first, 'desktop')
        await manager.connect(uid, second, 'desktop')
        manager.disconnect(uid, first)
        assert manager.desktop_presence([uid])[str(uid)] is True
        now[0] += 76
        assert manager.desktop_presence([uid])[str(uid)] is False
        manager.touch(uid, mobile)
        assert manager.desktop_presence([uid])[str(uid)] is False
        manager.touch(uid, second)
        assert manager.desktop_presence([uid])[str(uid)] is True
        manager.disconnect(uid, second)
        assert manager.desktop_presence([uid])[str(uid)] is False
        assert manager.desktop_presence([uuid4()]) != {}
    asyncio.run(scenario())


def test_old_clients_use_agent_and_ipad_report_overrides_mac_agent():
    from notification_ws import NotificationConnectionManager
    manager = NotificationConnectionManager()
    android, computer, ipad, unknown = [uuid4() for _ in range(4)]
    async def scenario():
        await manager.connect(android, Socket('Mozilla/5.0 Android'))
        await manager.connect(computer, Socket('Mozilla/5.0 Windows NT 10.0'))
        await manager.connect(ipad, Socket('Mozilla/5.0 Macintosh'), 'mobile')
        await manager.connect(unknown, Socket())
        states = manager.desktop_presence([android, computer, ipad, unknown])
        assert states == {str(android): False, str(computer): True, str(ipad): False, str(unknown): False}
    asyncio.run(scenario())


def test_presence_api_active_accounts_only_and_no_auth_bypass(environment, monkeypatch):
    db, (actor, online, inactive) = environment
    from routers.chat_sessions import PresenceRequest, desktop_presence
    import notification_ws
    manager = notification_ws.NotificationConnectionManager()
    monkeypatch.setattr(notification_ws, 'notification_manager', manager)
    asyncio.run(manager.connect(online.id, Socket('Windows'), 'desktop'))
    inactive.is_active = False; db.commit()
    result = desktop_presence(PresenceRequest(user_ids=[online.id, online.id, inactive.id, uuid4()]), db, actor)
    assert result['items'] == [dict(user_id=str(online.id), desktop_online=True)]
    with pytest.raises(HTTPException) as denied:
        desktop_presence(PresenceRequest(user_ids=[actor.id]), db, inactive)
    assert denied.value.status_code == 403
