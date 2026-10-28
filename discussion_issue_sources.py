from fastapi import HTTPException
from sqlalchemy import inspect
from discussion_chat_models import DiscussionIssueSource as Source, DiscussionMessage


def ready(db): return inspect(db.connection()).has_table(Source.__tablename__)


def preview(db, user, room_id, message_id, lock=False):
    from discussion_chat_service import require_room
    room = require_room(db,user,room_id)
    query = db.query(DiscussionMessage).filter_by(id=message_id,room_id=room_id)
    if lock: query = query.with_for_update().populate_existing()
    row = query.first()
    if row is None: raise HTTPException(404,'来源消息不存在')
    if row.recalled_at: raise HTTPException(409,'来源消息已撤回')
    if not row.content.strip(): raise HTTPException(422,'只能收录有文字的消息')
    return dict(source_message_id=None,source_type='discussion',source_conversation_id=room_id,
        source_title=room['name'],source_content=row.content,proposer_id=row.sender_id,proposer_name=row.sender_name,
        topic_id=None,topic_path='')


def for_issues(db, ids):
    return {row.issue_id:row for row in db.query(Source).filter(Source.issue_id.in_(ids))} if ids and ready(db) else {}


def decorate(result, source):
    if source:
        result.update(source_type='discussion',source_conversation_id=source.room_id,
            source_message_id=str(source.message_id))
