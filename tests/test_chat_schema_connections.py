"""连接池满载时的聊天能力检查；仅使用临时 SQLite 数据库。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

import chat_schema
import chat_topic_service
import chat_session_category_service
import discussion_chat_service


@pytest.mark.parametrize('workers', [1, 4])
def test_schema_checks_reuse_the_request_connection_when_pool_is_full(tmp_path, workers):
    engine = create_engine(f'sqlite:///{tmp_path / "chat.db"}', poolclass=QueuePool,
                          pool_size=workers, max_overflow=0, pool_timeout=.2,
                          connect_args={'check_same_thread': False})
    with engine.begin() as connection:
        for name in ('chat_direct_conversation', 'chat_project_member_pref', 'chat_direct_member',
                     'chat_mention_notification_target', 'chat_session_category', 'chat_session_category_link',
                     'chat_session_category_folder', 'chat_discussion_member', 'chat_discussion_message',
                     'chat_topic', 'chat_message_topic', 'chat_topic_audit'):
            connection.execute(text(f'CREATE TABLE {name} (id INTEGER)'))
        connection.execute(text('CREATE TABLE chat_project_message (direct_conversation_id INTEGER)'))
        connection.execute(text('CREATE TABLE chat_project_attachment (direct_conversation_id INTEGER)'))
        connection.execute(text('CREATE TABLE annotation_chat_member (pinned BOOLEAN, starred BOOLEAN)'))
    barrier = Barrier(workers)
    chat_schema._ready.cache_clear()
    def request(_):
        with Session(engine) as db:
            db.execute(text('SELECT 1'))
            barrier.wait(timeout=5)
            assert chat_schema.phase_one_ready(db)
            assert chat_session_category_service.schema_ready(db)
            assert chat_session_category_service.folder_schema_ready(db)
            assert discussion_chat_service.schema_ready(db)
            assert chat_topic_service.schema_ready(db)
            assert db.scalar(text('SELECT 1')) == 1
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(request, range(workers)))
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()
        chat_schema._ready.cache_clear()
