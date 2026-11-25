import asyncio
import json
import os
from contextlib import contextmanager
from pathlib import Path
import socket
import subprocess
import sys
from time import monotonic, sleep
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import httpx
import pytest
from redis import Redis
from sqlalchemy import text
from websockets.sync.client import connect

from chat_realtime_bus import ChatRealtimeBus, client_name_prefix, relay_payload
from test_chat_phase_one import environment  # noqa: F401


def test_relay_sends_only_chat_hints_to_target_users():
    origin, user, room, message = uuid4(), uuid4(), uuid4(), uuid4()
    delivered = []
    bus = object.__new__(ChatRealtimeBus)
    bus.origin = origin.hex

    async def deliver(recipients, payload):
        delivered.append((recipients, payload))

    bus.deliver = deliver
    local_message = {
        'type': 'chat_message', 'projectType': 'direct', 'projectId': str(room),
        'message': {'id': str(message), 'content': '正文留在 PostgreSQL'},
    }
    payload = relay_payload(local_message)
    envelope = {'origin': uuid4().hex, 'users': [str(user), str(user)], 'event': payload}

    async def scenario():
        await bus.receive(b'bad json')
        await bus.receive(json.dumps({**envelope, 'origin': origin.hex}).encode())
        await bus.receive(json.dumps({**envelope, 'users': ['invalid']}).encode())
        await bus.receive(json.dumps(envelope).encode())

    asyncio.run(scenario())
    assert relay_payload({'type': 'notification'}) is None
    assert delivered == [((user,), {
        'type': 'chat_remote_message_changed', 'projectType': 'direct', 'projectId': str(room),
        'messageId': str(message), 'kind': 'message', 'relayed': True,
    })]


@contextmanager
def backend(schema, name, tmp_path, settings):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    bootstrap = """
import os
import uvicorn
from database import engine
from psycopg2 import sql
from sqlalchemy import event

@event.listens_for(engine, 'connect')
def use_isolated_schema(connection, _):
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL('SET search_path TO {}, public').format(sql.Identifier(os.environ['CHAT_RELAY_TEST_SCHEMA'])))
    connection.commit()

uvicorn.run('main:app', host='127.0.0.1', port=int(os.environ['CHAT_RELAY_TEST_PORT']), access_log=False)
"""
    subprocess_env = dict(os.environ, **settings, CHAT_RELAY_TEST_SCHEMA=schema, CHAT_RELAY_TEST_PORT=str(port))
    log_path = tmp_path / f'{name}.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(
            [sys.executable, '-c', bootstrap], cwd=Path(__file__).resolve().parents[1],
            env=subprocess_env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False) as client:
                deadline = monotonic() + 30
                while True:
                    try:
                        if client.get('/', timeout=1).is_success:
                            break
                    except httpx.TransportError:
                        pass
                    if process.poll() is not None or monotonic() >= deadline:
                        pytest.fail(log_path.read_text(encoding='utf-8', errors='replace'))
                    sleep(.15)
                yield port, client
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)


def read_event(connection, matches, timeout=5):
    deadline = monotonic() + timeout
    while deadline > monotonic():
        frame = json.loads(connection.recv(timeout=deadline - monotonic()))
        if matches(frame):
            return frame
    pytest.fail('规定时间内没有收到目标会话事件')


def open_socket(port, token):
    query = urlencode({'token': token, 'client_type': 'mobile'})
    return connect(f'ws://127.0.0.1:{port}/notifications/ws?{query}', proxy=None)


def setup_rooms(db, users):
    from annotation_models import AnnotationProject
    from chat_session_category_models import ChatSessionCategory, ChatSessionCategoryFolder
    from discussion_chat_models import DiscussionMember
    from discussion_chat_service import RESOURCE_ROOT
    from models import AnnotationChatMember, ChatDirectConversation, ChatDirectMember, ChatProjectEnabled
    from models import ChatProjectMemberPref, RolePermission, TranslationProject, UserRole

    actor = users[0]
    role_id = db.query(UserRole.role_id).filter_by(user_id=actor.id).scalar()
    db.add_all(RolePermission(role_id=role_id, permission_code=code) for code in ('talents:read', 'workflow:operate'))
    direct = ChatDirectConversation(user_low_id=min(u.id for u in users[:2]), user_high_id=max(u.id for u in users[:2]))
    annotation = AnnotationProject(order_no='AP-REDIS', project_name='标注转发验收', created_by=actor.id)
    translation = TranslationProject(order_no='TP-REDIS', project_name='笔译转发验收', created_by=actor.id)
    discussion = ChatSessionCategory(name='讨论转发验收', updated_by=actor.id)
    db.add_all([direct, annotation, translation, discussion])
    db.flush()
    db.add(ChatSessionCategoryFolder(category_id=discussion.id, parent_key=RESOURCE_ROOT))
    db.add(ChatProjectEnabled(project_id=translation.id, enabled=True, enabled_by=actor.id))
    for user in users[:2]:
        db.add_all([
            ChatDirectMember(conversation_id=direct.id, user_id=user.id, last_read_sequence=0),
            AnnotationChatMember(project_id=annotation.id, user_id=user.id, following=True, last_read_sequence=0),
            ChatProjectMemberPref(project_id=translation.id, user_id=user.id, last_read_sequence=0),
            DiscussionMember(room_id=discussion.id, user_id=user.id),
        ])
    db.commit()
    return [
        ('direct', direct.id, f'/chat/direct/{direct.id}'),
        ('annotation', annotation.id, f'/project-chat/annotation/{annotation.id}'),
        ('translation', translation.id, f'/project-chat/{translation.id}'),
        ('discussion', discussion.id, f'/chat/discussions/{discussion.id}'),
    ]


def test_chat_relay_across_two_local_backends_and_catchup(environment, tmp_path):
    redis_url = os.getenv('CHAT_TEST_REDIS_URL')
    if not redis_url:
        pytest.skip('需要独立的本机 Redis，设置 CHAT_TEST_REDIS_URL')
    redis_host = urlsplit(redis_url).hostname
    assert redis_host in {'127.0.0.1', 'localhost', '::1'}

    from models import ChatProjectMessage
    from discussion_chat_models import DiscussionMessage
    from routers.auth import create_user_access_token

    db, users, _ = environment
    rooms = setup_rooms(db, users)
    tokens = [create_user_access_token(user) for user in users[:3]]
    schema = db.execute(text('select current_schema()')).scalar_one()
    channel = f'xinshi:test:chat:{uuid4().hex}'
    settings = dict(
        CHAT_REALTIME_REDIS_URL=redis_url, CHAT_REALTIME_CHANNEL=channel,
        CHAT_STORAGE_MODE='local', ANNOTATION_MATERIAL_STORAGE_MODE='disabled',
        LOCAL_SCHEMA_MIGRATIONS_ENABLED='false', VAPID_PUBLIC_KEY='', VAPID_PRIVATE_KEY='', VAPID_SUBJECT='',
    )

    def send(client, path, token, content):
        response = client.post(
            f'{path}/messages', headers={'Authorization': f'Bearer {token}'},
            json={'client_message_id': str(uuid4()), 'content': content},
        )
        assert response.status_code == 201, f'{path}: {response.text}'
        return response.json()

    with Redis.from_url(redis_url) as redis, backend(schema, 'cloud', tmp_path, settings) as cloud, backend(schema, 'lan', tmp_path, settings) as lan:
        deadline = monotonic() + 8
        while redis.pubsub_numsub(channel)[0][1] < 2:
            assert monotonic() < deadline, '两个本机后端未能订阅同一频道'
            sleep(.05)

        with open_socket(cloud[0], tokens[0]) as a, open_socket(lan[0], tokens[1]) as b, open_socket(lan[0], tokens[2]) as outsider:
            for connection in (a, b, outsider):
                read_event(connection, lambda event: event['type'] == 'snapshot')
            for kind, room, path in rooms:
                for (_, client), (_, reader), target, token, reader_token in (
                    (cloud, lan, b, tokens[0], tokens[1]), (lan, cloud, a, tokens[1], tokens[0]),
                ):
                    row = send(client, path, token, f'{kind} 双向发送测试')
                    event = read_event(target, lambda item: item.get('relayed') and item.get('projectId') == str(room)
                                       and item.get('type') in {'chat_remote_message_changed', 'chat_sessions_changed'})
                    assert 'message' not in event and 'content' not in event
                    if kind != 'discussion':
                        assert event['messageId'] == row['id']
                    timeline = 'timeline' if kind in {'direct', 'annotation'} else 'messages'
                    response = reader.get(f'{path}/{timeline}', headers={'Authorization': f'Bearer {reader_token}'})
                    assert response.status_code == 200
                    assert any(item['id'] == row['id'] and item['content'] == row['content']
                               for item in response.json()['items'])
            with pytest.raises(TimeoutError):
                outsider.recv(timeout=.25)

            # 测试只断开这条测试频道的订阅，浏览器 WebSocket 保持打开。
            subscribers = [item for item in redis.client_list(_type='pubsub')
                           if item['name'].startswith(client_name_prefix(channel))]
            assert len(subscribers) == 2
            for subscriber in subscribers:
                redis.client_kill_filter(_id=subscriber['id'])
            for connection in (a, b):
                read_event(connection, lambda event: event['type'] == 'chat_realtime_recovered')

        direct_path = rooms[0][2]
        anchor = send(cloud[1], direct_path, tokens[0], '补拉前的游标')
        missing = send(cloud[1], direct_path, tokens[0], '接收端断线期间的消息')
        with open_socket(lan[0], tokens[1]) as recovered:
            read_event(recovered, lambda event: event['type'] == 'snapshot')
            response = lan[1].get(f'{direct_path}/timeline', params={'after': anchor['sequence_no']},
                                  headers={'Authorization': f'Bearer {tokens[1]}'})
            assert response.status_code == 200
            assert [item['id'] for item in response.json()['items']] == [missing['id']]

        assert db.query(ChatProjectMessage).count() == 8
        assert db.query(DiscussionMessage).count() == 2
