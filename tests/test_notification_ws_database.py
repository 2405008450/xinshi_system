"""WebSocket 同步数据库调用不得阻塞事件循环；不连接业务数据库。"""
import asyncio
import json
from threading import get_ident
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, WebSocketDisconnect
import annotation_chat_service
import routers.notifications as api


@pytest.fixture(autouse=True)
def isolate_shared_presence(monkeypatch):
    monkeypatch.setattr(api, '_publish_socket_presence', lambda *args: True)


def test_socket_db_work_uses_workers_and_releases_sessions_before_sending(monkeypatch):
    main_thread = get_ident()
    threads, active, closed, sent = [], [], [], []
    user_id = uuid4()
    class Session:
        def __enter__(self):
            assert get_ident() != main_thread
            active.append(self)
            return self
        def __exit__(self, *_):
            active.remove(self); closed.append(self)
    def authenticate(db, token):
        threads.append(get_ident())
        assert token == 'test-token' and db in active
        return SimpleNamespace(id=user_id)
    monkeypatch.setattr(api, 'SessionLocal', Session)
    monkeypatch.setattr(api, 'get_user_from_token_value', authenticate)
    monkeypatch.setattr(api, 'count_unread_notifications', lambda *a, **kw: 0)
    class Socket:
        messages = iter(['ping'])
        async def accept(self):
            assert not active
        async def send_json(self, payload):
            assert not active
            sent.append(payload['type'])
        async def receive_text(self):
            try: return next(self.messages)
            except StopIteration: raise WebSocketDisconnect()
        async def close(self, code):
            raise AssertionError(f'unexpected close {code}')
    asyncio.run(api.notifications_ws(Socket(), 'test-token'))
    assert threads and all(thread != main_thread for thread in threads)
    assert len(closed) == 2 and not active
    assert sent == ['snapshot', 'pong']
    assert str(user_id) not in api.notification_manager.active_connections


def test_invalid_socket_token_still_closes_connection(monkeypatch):
    class Session:
        def __enter__(self): return self
        def __exit__(self, *_): pass
    monkeypatch.setattr(api, 'SessionLocal', Session)
    monkeypatch.setattr(api, 'get_user_from_token_value', lambda *args: None)
    closed = []
    class Socket:
        async def close(self, code): closed.append(code)
    asyncio.run(api.notifications_ws(Socket(), 'invalid'))
    assert closed == [1008]


def test_idle_desktop_is_probed_and_reply_refreshes_presence(monkeypatch):
    from notification_ws import NotificationConnectionManager
    user_id = uuid4()
    manager = NotificationConnectionManager()
    monkeypatch.setattr(api, 'notification_manager', manager)
    monkeypatch.setattr(api, '_socket_snapshot', lambda token: (user_id, 0, 0))
    monkeypatch.setattr(api, '_socket_token_valid', lambda token: True)
    sent, writes = [], []
    monkeypatch.setattr(api, '_publish_socket_presence', lambda *args: writes.append(args))
    calls = 0
    async def wait_for(awaitable, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            awaitable.close()
            raise asyncio.TimeoutError()
        return await awaitable
    monkeypatch.setattr(api.asyncio, 'wait_for', wait_for)
    class Socket:
        headers = {'user-agent': 'Windows'}
        async def accept(self): pass
        async def send_json(self, payload): sent.append(payload['type'])
        async def receive_text(self):
            if calls == 2: return 'ping'
            raise WebSocketDisconnect()
        async def close(self, code): raise AssertionError(code)
    asyncio.run(api.notifications_ws(Socket(), 'test', 'desktop'))
    assert sent == ['snapshot', 'ping', 'pong']
    assert [entry[2:] for entry in writes] == [(1, True), (2, True), (3, True), (4, False)]
    assert manager.desktop_presence([user_id])[str(user_id)] is False


@pytest.mark.parametrize('agent,client_type,expected', [('Windows NT 10.0','',True),('Macintosh','mobile',False),('iPhone','',False)])
def test_server_collects_old_desktop_clients_without_new_http_heartbeat(monkeypatch,agent,client_type,expected):
    user_id=uuid4();writes=[];main_thread=get_ident()
    monkeypatch.setattr(api,'_socket_snapshot',lambda token:(user_id,0,0))
    monkeypatch.setattr(api,'_socket_token_valid',lambda token:True)
    def publish(*args):
        assert get_ident()!=main_thread
        writes.append(args)
        return True
    monkeypatch.setattr(api,'_publish_socket_presence',publish)
    class Socket:
        headers={'user-agent':agent}
        messages=iter(['ping'])
        async def accept(self):pass
        async def send_json(self,payload):pass
        async def receive_text(self):
            try:return next(self.messages)
            except StopIteration:raise WebSocketDisconnect()
        async def close(self,code):raise AssertionError(code)
    asyncio.run(api.notifications_ws(Socket(),'isolated-token',client_type))
    if expected:
        assert [entry[2:] for entry in writes]==[(1,True),(2,True),(3,False)]
        assert len({entry[1] for entry in writes})==1
        assert {entry[0] for entry in writes}=={user_id}
    else:assert writes==[]


@pytest.mark.parametrize('denied', [False, True])
def test_annotation_watch_keeps_project_authorization_in_worker(monkeypatch, denied):
    user_id, project_id, main_thread = uuid4(), uuid4(), get_ident()
    checks, sent = [], []
    class Session:
        def __enter__(self): return self
        def __exit__(self, *_): pass
    def require_project(db, pid, user):
        assert get_ident() != main_thread
        checks.append((pid, user.id))
        if denied: raise HTTPException(403, '没有项目查看权限')
    monkeypatch.setattr(api, 'SessionLocal', Session)
    monkeypatch.setattr(api, 'get_user_from_token_value', lambda *args: SimpleNamespace(id=user_id))
    monkeypatch.setattr(api, 'count_unread_notifications', lambda *a, **kw: 0)
    monkeypatch.setattr(annotation_chat_service, 'require_project', require_project)
    class Socket:
        messages = iter([json.dumps({'type': 'annotation_chat_watch', 'projectId': str(project_id), 'active': True})])
        async def accept(self): pass
        async def send_json(self, payload): sent.append(payload['type'])
        async def receive_text(self):
            try: return next(self.messages)
            except StopIteration: raise WebSocketDisconnect()
        async def close(self, code): raise AssertionError(code)
    asyncio.run(api.notifications_ws(Socket(), 'test'))
    assert checks == [(project_id, user_id)]
    assert ('annotation_chat_watch_error' in sent) == denied
    assert str(user_id) not in api.notification_manager.active_connections
