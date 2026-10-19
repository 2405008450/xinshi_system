from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from database import get_db
from routers.auth import get_current_user
from chat_topic_models import ChatTopic
from chat_topic_schemas import TopicCreate, TopicUpdate, MessageTopicWrite
import chat_topic_service as service

router = APIRouter(prefix='/chat/topics', tags=['chat_topics'])


def actor(user=Depends(get_current_user)):
    if not user.is_active:
        raise HTTPException(403, '账号已停用')
    return user


def ready(db=Depends(get_db)):
    service.require_ready(db)
    return db


def commit(db):
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, '同一层级已有同名讨论主题') from error


@router.get('')
def tree(db=Depends(get_db), user=Depends(actor)):
    caps = service.capabilities(db, user)
    rows = service.topic_rows(db) if caps['ready'] else []
    index = {row.id: row for row in rows}
    return dict(**caps, items=[service.serialize_topic(row, index) for row in rows])


@router.post('', status_code=201)
def create(payload: TopicCreate, db=Depends(ready), user=Depends(actor)):
    if not service.capabilities(db, user)['can_manage']:
        raise HTTPException(403, '没有主题菜单维护权限')
    if payload.parent_id:
        parent = service.get_topic(db, payload.parent_id, selecting=True)
        if parent.parent_id:
            raise HTTPException(422, '讨论主题最多支持两级')
    row = ChatTopic(**payload.model_dump())
    db.add(row)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, '同一层级已有同名讨论主题') from error
    index = {value.id: value for value in service.topic_rows(db)}
    result = service.serialize_topic(row, index)
    service.audit(db, user, row.id, 'topic.create', {}, result)
    commit(db)
    service.notify_menu_changed(db)
    return result


@router.put('/{topic_id}')
def update(topic_id: UUID, payload: TopicUpdate, db=Depends(ready), user=Depends(actor)):
    if not service.capabilities(db, user)['can_manage']:
        raise HTTPException(403, '没有主题菜单维护权限')
    row = db.query(ChatTopic).filter_by(id=topic_id).with_for_update().first()
    if not row:
        raise HTTPException(404, '讨论主题不存在')
    if row.revision != payload.revision:
        raise HTTPException(409, '菜单已被其他人修改，请重新加载')
    if row.kind == 'annotation' and (payload.name != row.name or not payload.active):
        raise HTTPException(422, '内置标注项目入口不能改名或停用')
    index = {value.id: value for value in service.topic_rows(db)}
    before = service.serialize_topic(row, index)
    for key, value in payload.model_dump(exclude={'revision'}).items():
        setattr(row, key, value)
    row.revision += 1
    row.updated_at = service.topic_now()
    after = service.serialize_topic(row, index)
    service.audit(db, user, row.id, 'topic.update', before, after)
    commit(db)
    service.notify_menu_changed(db)
    return after


@router.put('/messages/{message_id}')
def classify(message_id: UUID, payload: MessageTopicWrite, db=Depends(ready), user=Depends(actor)):
    message = service.require_message(db, user, message_id, lock=True)
    service.set_message_topic(db, user, message, payload.topic_id, payload.revision)
    db.commit()
    result = service.message_metadata(message, user.id)
    if message.direct_conversation_id:
        from direct_chat_service import publish
        publish(db, message.direct_conversation_id, 'topic', message.id)
    elif message.annotation_project_id:
        from annotation_chat_service import publish
        publish(db, message.annotation_project_id, 'topic', message.id)
    else:
        from annotation_chat_service import eligible_users
        from notification_ws import broadcast_to_users
        broadcast_to_users([person.id for person in eligible_users(db)], {'type': 'chat_message_topic_changed',
            'projectType': 'translation', 'projectId': str(message.project_id), 'messageId': str(message.id)})
    return result


@router.get('/messages/{message_id}')
def message_topic(message_id: UUID, db=Depends(ready), user=Depends(actor)):
    return service.message_metadata(service.require_message(db, user, message_id), user.id)


@router.get('/search')
def search(topic_id: UUID, scope: Literal['current', 'all'] = 'current',
           conversation_type: Literal['translation', 'annotation', 'direct'] | None = None,
           conversation_id: UUID | None = None, keyword: str = Query('', max_length=255),
           before: int | None = Query(None, ge=1), limit: int = Query(30, ge=1, le=100),
           db=Depends(ready), user=Depends(actor)):
    return service.search(db, user, topic_id, scope, conversation_type, conversation_id, keyword, before, limit)
