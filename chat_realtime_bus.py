"""跨后端发送会话变更提示，消息内容由已授权的 HTTP 接口读取。"""
import asyncio
import json
import logging
import random
from hashlib import sha256
from time import monotonic
from uuid import UUID, uuid4

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError


DEFAULT_CHANNEL = 'xinshi:chat:events:v1'
MAX_EVENT_BYTES = 128 * 1024
MAX_EVENT_AGE_SECONDS = 5
CHAT_EVENTS = {
    'annotation_chat_changed', 'direct_chat_changed', 'chat_sessions_changed',
    'chat_conversation_removed', 'chat_topics_changed', 'chat_message_topic_changed',
    'chat_message_acknowledgement', 'chat_remote_message_changed', 'chat_mention_changed',
}
EVENT_FIELDS = (
    'type', 'projectType', 'projectId', 'messageId', 'kind', 'membersChanged',
    'userId', 'userName', 'acknowledged', 'acknowledgedAt',
)


def client_name_prefix(channel):
    return f'xinshi-chat-{sha256(channel.encode()).hexdigest()[:16]}-'


def relay_payload(payload):
    event = payload.get('type')
    if event in ('chat_message', 'chat_message_edited'):
        message = payload.get('message') or {}
        return relay_payload({
            'type': 'chat_remote_message_changed',
            'projectType': payload.get('projectType'),
            'projectId': payload.get('projectId'),
            'messageId': payload.get('messageId') or message.get('id'),
            'kind': 'edit' if event == 'chat_message_edited' else 'message',
        })
    if event not in CHAT_EVENTS:
        return None
    return {key: payload[key] for key in EVENT_FIELDS
            if key in payload and isinstance(payload[key], (str, bool, type(None)))}


class ChatRealtimeBus:
    def __init__(self, url, channel, deliver, recovered):
        self.loop = asyncio.get_running_loop()
        self.origin = uuid4().hex
        self.channel = channel
        self.deliver = deliver
        self.recovered = recovered
        self.queue = asyncio.Queue(maxsize=1024)
        self.client = Redis.from_url(
            url, protocol=2, socket_connect_timeout=2, socket_timeout=3,
            health_check_interval=15, retry=Retry(NoBackoff(), 0), max_connections=2,
            client_name=client_name_prefix(channel) + self.origin,
        )
        self.last_warning = -float('inf')
        self.stopped = False
        self.tasks = [
            self.loop.create_task(self.publish(), name='chat-redis-publisher'),
            self.loop.create_task(self.subscribe(), name='chat-redis-subscriber'),
        ]

    def enqueue(self, recipients, payload):
        event = relay_payload(payload)
        if not event or self.stopped:
            return
        try:
            self.loop.call_soon_threadsafe(self.offer, recipients, event)
        except RuntimeError:
            # 关停时数据库已写入，客户端仍可补拉。
            pass

    def offer(self, recipients, event):
        if self.stopped:
            return
        try:
            self.queue.put_nowait((monotonic(), recipients, event))
        except asyncio.QueueFull:
            self.warn('队列已满')

    def warn(self, reason):
        now = monotonic()
        if now - self.last_warning >= 30:
            self.last_warning = now
            logging.getLogger(__name__).warning('聊天实时转发暂不可用（%s），消息可通过会话接口补拉', reason)

    async def publish(self):
        while True:
            enqueued_at, recipients, event = await self.queue.get()
            if monotonic() - enqueued_at > MAX_EVENT_AGE_SECONDS:
                continue
            wire = json.dumps(
                {'origin': self.origin, 'users': [str(uid) for uid in recipients], 'event': event},
                ensure_ascii=False, separators=(',', ':'),
            ).encode('utf-8')
            if len(wire) > MAX_EVENT_BYTES:
                self.warn('事件过大')
                continue
            try:
                await self.client.publish(self.channel, wire)
            except (RedisError, OSError) as exc:
                self.warn(type(exc).__name__)
                # Redis 不可用时让发送接口继续运行，恢复后由数据库补拉。
                await asyncio.sleep(1)

    async def receive(self, raw):
        if isinstance(raw, str):
            raw = raw.encode('utf-8')
        if not isinstance(raw, bytes) or len(raw) > MAX_EVENT_BYTES:
            return
        try:
            data = json.loads(raw)
            if data['origin'] == self.origin:
                return
            payload = relay_payload(data['event'])
            recipients = tuple(dict.fromkeys(UUID(value) for value in data['users']))
        except (AttributeError, KeyError, TypeError, ValueError):
            return
        if payload and recipients:
            await self.deliver(recipients, {**payload, 'relayed': True})

    async def subscribe(self):
        should_recover = False
        while True:
            try:
                async with self.client.pubsub() as subscriber:
                    await subscriber.subscribe(self.channel)
                    while True:
                        packet = await subscriber.get_message(timeout=1)
                        if packet is None:
                            continue
                        if packet['type'] == 'subscribe':
                            if should_recover:
                                await self.recovered()
                            should_recover = True
                        elif packet['type'] == 'message':
                            await self.receive(packet['data'])
            except (RedisError, OSError) as exc:
                should_recover = True
                self.warn(type(exc).__name__)
                await asyncio.sleep(1 + random.random())

    async def close(self):
        self.stopped = True
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.client.aclose()
