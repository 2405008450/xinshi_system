"""跨后端/多页面共享在线状态；只使用隔离 SQLite。"""
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from chat_time import now
from chat_presence_registry import ChatDesktopHeartbeat, record, desktop_presence
from tools.apply_chat_presence_migration import apply_migration


@pytest.fixture
def engine():
    import main  # noqa: F401 注册所有 ORM，不执行启动钩子。
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        apply_migration(connection)
        apply_migration(connection)
    yield engine
    engine.dispose()


def test_other_process_reads_heartbeat_and_absent_is_unknown(engine):
    user,other,client=uuid4(),uuid4(),uuid4()
    with Session(engine) as writer:
        assert record(writer,user,client,1)
    with Session(engine) as reader:
        assert desktop_presence(reader,[user,other])=={str(user):True,str(other):None}


def test_multiple_computers_disconnect_sequence_and_expiry(engine):
    user,a,b=uuid4(),uuid4(),uuid4();moment=now()
    with Session(engine) as db:
        record(db,user,a,1,moment=moment)
        record(db,user,b,1,moment=moment)
        record(db,user,a,3,False,moment=moment)
        record(db,user,a,2,True,moment=moment+timedelta(seconds=1))
        assert db.get(ChatDesktopHeartbeat,(user,a)).active is False
        assert desktop_presence(db,[user],moment)[str(user)] is True
        record(db,user,b,2,False,moment=moment)
        assert desktop_presence(db,[user],moment)[str(user)] is False
        record(db,user,b,3,moment=moment)
        assert desktop_presence(db,[user],moment+timedelta(seconds=119))[str(user)] is True
        assert desktop_presence(db,[user],moment+timedelta(seconds=120))[str(user)] is False


def test_missing_table_does_not_claim_offline():
    engine=create_engine('sqlite://');uid=uuid4()
    with Session(engine) as db:
        assert record(db,uid,uuid4(),1) is False
        assert desktop_presence(db,[uid])=={str(uid):None}
    engine.dispose()


def test_authenticated_route_rejects_mobile_and_records_only_current_user(engine):
    from types import SimpleNamespace
    from starlette.requests import Request
    from routers.chat_sessions import desktop_heartbeat,PresenceHeartbeat
    uid,client=uuid4(),uuid4()
    actor=SimpleNamespace(id=uid,is_active=True,is_deleted=False)
    body=PresenceHeartbeat(client_id=client,sequence=1)
    request=lambda ua:Request({'type':'http','headers':[(b'user-agent',ua)]})
    with Session(engine) as db:
        assert desktop_heartbeat(body,request(b'iPhone Mobile'),db,actor)=={'recorded':False}
        assert desktop_presence(db,[uid])[str(uid)] is None
        assert desktop_heartbeat(body,request(b'Mozilla/5.0 (Windows NT 10.0)'),db,actor)=={'recorded':True}
        assert desktop_presence(db,[uid])[str(uid)] is True
        assert set(inspect(engine).get_table_names())=={'chat_desktop_heartbeat'}


def test_socket_collector_is_visible_to_another_backend_and_storage_failure_is_nonfatal(engine,monkeypatch):
    import routers.notifications as api
    from sqlalchemy.exc import OperationalError
    uid,client=uuid4(),uuid4()
    monkeypatch.setattr(api,'SessionLocal',lambda:Session(engine))
    assert api._publish_socket_presence(uid,client,1,True)
    with Session(engine) as reader:
        assert desktop_presence(reader,[uid])[str(uid)] is True
    assert api._publish_socket_presence(uid,client,2,False)
    with Session(engine) as reader:
        assert desktop_presence(reader,[uid])[str(uid)] is False
    def unavailable():raise OperationalError('isolated',{},Exception('unavailable'))
    monkeypatch.setattr(api,'SessionLocal',unavailable)
    assert api._publish_socket_presence(uid,client,3,True) is False
