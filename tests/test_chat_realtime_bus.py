import asyncio
import json
import os
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
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


def test_chat_send_lock_timeout_and_cross_backend_retry(environment, tmp_path):
    from discussion_chat_models import DiscussionMessage
    from models import AppNotification
    from routers.auth import create_user_access_token

    db, users, engine = environment
    _, room, path = next(room for room in setup_rooms(db, users) if room[0] == 'discussion')
    schema = db.execute(text('select current_schema()')).scalar_one()
    headers = {'Authorization': 'Bearer ' + create_user_access_token(users[0])}
    payload = {'client_message_id': str(uuid4()), 'content': '锁释放后重试发送'}
    settings = dict(
        CHAT_REALTIME_REDIS_URL='', CHAT_STORAGE_MODE='local', LOCAL_SCHEMA_MIGRATIONS_ENABLED='false',
        VAPID_PUBLIC_KEY='', VAPID_PRIVATE_KEY='', VAPID_SUBJECT='',
    )
    with backend(schema, 'sender-cloud', tmp_path, settings) as cloud, backend(schema, 'sender-lan', tmp_path, settings) as lan:
        with engine.begin() as blocker:
            blocker.execute(text('SELECT pg_advisory_xact_lock(:room)'), {'room': room.int & ((1 << 63) - 1)})
            blocked = cloud[1].post(f'{path}/messages', headers=headers, json=payload, timeout=8)
            assert blocked.status_code == 503, blocked.text
            assert blocked.headers['Retry-After'] == '1'
            assert db.query(DiscussionMessage).filter_by(room_id=room).count() == 0

        def retry(client):
            response = client.post(f'{path}/messages', headers=headers, json=payload, timeout=8)
            assert response.status_code == 201, response.text
            return response.json()['id']

        with ThreadPoolExecutor(max_workers=2) as pool:
            message_ids = list(pool.map(retry, [lan[1], cloud[1]]))
        assert message_ids[0] == message_ids[1]
        assert db.query(DiscussionMessage).filter_by(room_id=room).count() == 1
        assert db.query(AppNotification).filter_by(related_entity_id=room, notification_type='discussion_chat').count() == 1


def test_chat_pin_and_star_ignore_notification_locks(environment, tmp_path):
    from discussion_chat_models import DiscussionMember
    from models import AppNotification, ChatDirectMember
    from routers.auth import create_user_access_token

    db, users, engine = environment
    rooms = {kind: (room, path) for kind, room, path in setup_rooms(db, users)}
    schema = db.execute(text('select current_schema()')).scalar_one()
    sender, reader = [{'Authorization': 'Bearer ' + create_user_access_token(user)} for user in users[:2]]
    settings = dict(
        CHAT_REALTIME_REDIS_URL='', CHAT_STORAGE_MODE='local', LOCAL_SCHEMA_MIGRATIONS_ENABLED='false',
        DB_LOCK_TIMEOUT_MS='250', VAPID_PUBLIC_KEY='', VAPID_PRIVATE_KEY='', VAPID_SUBJECT='',
    )
    with backend(schema, 'preferences', tmp_path, settings) as (_, client):
        for kind, model in [('discussion', DiscussionMember), ('direct', ChatDirectMember)]:
            room, path = rooms[kind]
            sent = client.post(f'{path}/messages', headers=sender, json={
                'client_message_id': str(uuid4()), 'content': '测试置顶时通知正在被锁住',
            })
            assert sent.status_code == 201, sent.text
            message = sent.json()
            notice = db.query(AppNotification).filter_by(related_entity_id=room, recipient_user_id=users[1].id).one()
            member = db.get(model, (room, users[1].id))
            if kind == 'discussion':
                member.last_read_id = int(message['id'])
                preference_path = f'{path}/preferences'
            else:
                member.last_read_sequence = message['sequence_no']
                preference_path = f'/chat/sessions/{kind}/{room}/preferences'
            db.commit()

            with engine.begin() as blocker:
                blocker.execute(text('SELECT id FROM app_notification WHERE id = :id FOR UPDATE'), {'id': notice.id})
                for field, enabled in [('pinned', True), ('starred', True), ('pinned', False)]:
                    response = client.put(preference_path, headers=reader, json={field: enabled})
                    assert response.status_code == 200, response.text
                    assert response.json()[field] is enabled
                db.refresh(notice)
                assert not notice.is_read
                response = client.put(preference_path, headers=reader, json={'read_message_id': message['id']})
                assert response.status_code == 503, response.text
                assert response.headers['Retry-After'] == '1'

            response = client.put(preference_path, headers=reader, json={'read_message_id': message['id']})
            assert response.status_code == 200, response.text
            db.refresh(notice)
            assert notice.is_read
            assert response.json()['starred'] is True and response.json()['pinned'] is False


def test_chat_pin_succeeds_during_concurrent_read_and_project_locks(environment, tmp_path):
    from models import AppNotification
    from routers.auth import create_user_access_token

    db, users, engine = environment
    rooms = {kind: (room, path) for kind, room, path in setup_rooms(db, users)}
    discussion, path = rooms['discussion']
    schema = db.execute(text('select current_schema()')).scalar_one()
    sender, reader = [{'Authorization': 'Bearer ' + create_user_access_token(user)} for user in users[:2]]
    settings = dict(CHAT_REALTIME_REDIS_URL='', CHAT_STORAGE_MODE='local', LOCAL_SCHEMA_MIGRATIONS_ENABLED='false',
                    VAPID_PUBLIC_KEY='', VAPID_PRIVATE_KEY='', VAPID_SUBJECT='')
    pin_settings = dict(settings, DB_LOCK_TIMEOUT_MS='350')
    read_settings = dict(settings, DB_LOCK_TIMEOUT_MS='8000')
    with (backend(schema, 'pin', tmp_path, pin_settings) as (_, writer),
          backend(schema, 'reader', tmp_path, read_settings) as (_, read_client),
          ThreadPoolExecutor(max_workers=1) as pool):
        response = writer.post(f'{path}/messages', headers=sender, json={
            'client_message_id': str(uuid4()), 'content': '并发已读时的置顶测试',
        })
        assert response.status_code == 201, response.text
        message_id = response.json()['id']
        notification_id = db.query(AppNotification.id).filter_by(
            related_entity_id=discussion, recipient_user_id=users[1].id,
        ).scalar()
        preference_path = f'{path}/preferences'
        with engine.begin() as blocker:
            blocker.execute(text('SELECT id FROM app_notification WHERE id = :id FOR UPDATE'), {'id': notification_id})
            pending = pool.submit(read_client.put, preference_path, headers=reader, json={'read_message_id': message_id})
            deadline = monotonic() + 4
            with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as observer:
                while not observer.execute(text(
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE wait_event_type = 'Lock' "
                    "AND query LIKE 'UPDATE app_notification%')",
                )).scalar_one():
                    assert monotonic() < deadline, '已读请求未进入预期的通知锁等待'
                    sleep(.04)
            pinned = writer.put(preference_path, headers=reader, json={'pinned': True})
            assert pinned.status_code == 200, pinned.text
            assert pinned.json()['pinned'] is True and not pending.done()
        finished = pending.result()
        assert finished.status_code == 200 and finished.json()['last_read_id'] == message_id
        assert finished.json()['pinned'] is True

        for kind, table in [('direct', 'chat_direct_conversation'), ('annotation', 'annotation_project'),
                            ('translation', 'translation_project')]:
            project, _ = rooms[kind]
            with engine.begin() as blocker:
                blocker.execute(text(f'SELECT id FROM {table} WHERE id = :id FOR UPDATE'), {'id': project})
                result = writer.put(f'/chat/sessions/{kind}/{project}/preferences', headers=reader, json={'pinned': True})
                assert result.status_code == 200, result.text
                assert result.json()['pinned'] is True


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
                    key = f'{kind}:{room}'
                    response = reader.get('/chat/sessions/updates', params={'keys': f'{key},{key}'},
                                          headers={'Authorization': f'Bearer {reader_token}'})
                    assert response.status_code == 200, response.text
                    summary, = response.json()['items']
                    assert summary['key'] == key and summary['last_message']['id'] == row['id']
                    assert summary['unread'] >= 1
                response = lan[1].get('/chat/sessions/updates', params={'keys': f'{kind}:{room}'},
                                      headers={'Authorization': f'Bearer {tokens[2]}'})
                assert response.status_code == 200
                assert response.json() == {'items': []}
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
            response = lan[1].put(f'{direct_path}/read', json={'message_id': missing['id']},
                                 headers={'Authorization': f'Bearer {tokens[1]}'})
            assert response.status_code == 200
            response = cloud[1].get('/chat/sessions/updates', params={'keys': f'direct:{rooms[0][1]}'},
                                    headers={'Authorization': f'Bearer {tokens[1]}'})
            assert response.status_code == 200
            assert response.json()['items'][0]['unread'] == 0

        assert db.query(ChatProjectMessage).count() == 8
        assert db.query(DiscussionMessage).count() == 2
