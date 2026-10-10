"""迁移前保持原聊天可用；能力探测只读，不在服务启动修改结构。"""
from functools import lru_cache
from sqlalchemy import inspect
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db


@lru_cache(maxsize=8)
def _ready(bind):
    inspector = inspect(bind)
    return (inspector.has_table('chat_direct_conversation')
        and inspector.has_table('chat_project_member_pref')
        and inspector.has_table('chat_direct_member')
        and inspector.has_table('chat_mention_notification_target')
        and 'direct_conversation_id' in {c['name'] for c in inspector.get_columns('chat_project_message')}
        and 'direct_conversation_id' in {c['name'] for c in inspector.get_columns('chat_project_attachment')}
        and {'pinned', 'starred'} <= {c['name'] for c in inspector.get_columns('annotation_chat_member')})


def phase_one_ready(db):
    return _ready(db.get_bind())


def require_phase_one(db: Session = Depends(get_db)):
    if not phase_one_ready(db):
        raise HTTPException(503, '聊天第一阶段尚未完成数据库迁移，现有项目沟通仍可使用')
