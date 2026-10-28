from fastapi import HTTPException
from sqlalchemy import inspect
from discussion_chat_models import DiscussionMessageAction as Action
from chat_time import now, api_time


def ready(db):
    return inspect(db.connection()).has_table(Action.__tablename__)


def load(db, ids, user_id):
    if not ids or not ready(db): return {}
    grouped = {}
    for row in db.query(Action).filter(Action.message_id.in_(ids)).all():
        data = grouped.setdefault(row.message_id, dict(is_favorited=False, is_acknowledged=False, acknowledgements=[]))
        if row.user_id == user_id:
            data.update(is_favorited=bool(row.favorited_at), is_acknowledged=bool(row.acknowledged_at))
        if row.acknowledged_at:
            data['acknowledgements'].append(api_time(dict(user_id=row.user_id,user_name=row.user_name,acknowledged_at=row.acknowledged_at)))
    return grouped


def set_action(db, user, room_id, message_id, action, enabled):
    from chat_message_interactions import scope
    query, model, _ = scope(db,'discussion',room_id,user)
    message = query.filter(model.id == message_id).with_for_update().first()
    if not message or message.recalled_at: raise HTTPException(404,'消息不存在或已撤回')
    if action == 'acknowledgement' and message.sender_id == user.id: raise HTTPException(400,'不能确认收到自己的消息')
    if not ready(db): raise HTTPException(503,'讨论消息操作尚未初始化')
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
    db.execute(insert(Action).values(message_id=message_id,user_id=user.id,user_name=user.full_name or user.username).on_conflict_do_nothing())
    row = db.get(Action,(message_id,user.id))
    field='favorited_at' if action == 'favorite' else 'acknowledged_at'
    setattr(row,field,(getattr(row,field) or now()) if enabled else None)
    db.commit()
    import discussion_chat_service as service
    service.publish(db)
    return service.serialize(db,message,user)
