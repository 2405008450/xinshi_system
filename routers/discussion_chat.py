
from starlette.concurrency import run_in_threadpool
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, File, UploadFile
from pydantic import BaseModel, ConfigDict, Field, model_validator
from database import get_db
from routers.chat_topics import actor
import discussion_chat_service as service

router = APIRouter(prefix='/chat/discussions', tags=['discussion_chat'])


@router.post('/{room_id}/files', status_code=201)
async def upload_file(room_id: UUID, request: Request, file: UploadFile = File(...), db=Depends(get_db), user=Depends(actor)):
    from chat_common_handlers import upload_chat_file
    class Access:
        @staticmethod
        def require_project(db, id, user):
            service.require_room(db, user, id)
    return await upload_chat_file(Access, 'discussion', room_id, request, file, db, user)


@router.get('/{room_id}/files/{attachment_id}')
async def read_file(room_id: UUID, attachment_id: UUID, request: Request, info: bool = False, db=Depends(get_db), user=Depends(actor)):
    def prepare():
        from discussion_chat_files import require_file
        from discussion_chat_models import DiscussionMessage
        from routers.project_chat import get_chat_upload_dir
        from fastapi.responses import FileResponse
        service.require_room(db, user, room_id)
        row = require_file(db, room_id, attachment_id)
        if row.uploaded_by != user.id:
            ref = f'[附件](discussion-file://{attachment_id})'
            message = db.query(DiscussionMessage.id).filter(DiscussionMessage.room_id == room_id,
                DiscussionMessage.recalled_at.is_(None), DiscussionMessage.content.contains(ref, autoescape=True)).first()
            if not message:
                raise HTTPException(404, '附件消息不存在或已撤回')
        if info:
            return {'name': row.original_name, 'size': row.file_size}
        from chat_attachment_storage import remote_attachment_url, read_remote_attachment
        remote = remote_attachment_url()
        if remote:
            return None
        path = get_chat_upload_dir() / row.storage_name
        if not path.is_file():
            raise HTTPException(404, '附件文件不存在')
        return FileResponse(path, filename=row.original_name, media_type=row.content_type,
            headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    result = await run_in_threadpool(prepare)
    from chat_attachment_storage import remote_attachment_url, read_remote_attachment
    remote = remote_attachment_url()
    if result is None:
        target = remote.removesuffix('/project-chat/attachments') + f'/chat/discussions/{room_id}/files'
        return await read_remote_attachment(target, attachment_id, request.headers.get('authorization'),
            request.headers.get('x-chat-attachment-forwarded'), allow_files=True)
    return result


class DiscussionNameWrite(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    revision: int | None = Field(default=None, ge=1)


@router.put('/{room_id}/name')
def rename(room_id: UUID, payload: DiscussionNameWrite, db=Depends(get_db), user=Depends(actor)):
    from technical_requirements import ready as technical_ready
    from technical_requirement_models import TechnicalRoom
    if technical_ready(db) and db.query(TechnicalRoom).filter_by(room_id=room_id).first():
        raise HTTPException(403,'技术需求会话名称随项目自动生成，请编辑项目名称')
    import chat_session_category_service as categories
    from chat_session_category_models import ChatSessionCategory, ChatSessionCategoryFolder, category_now
    categories.require_manager(db, user)
    room = service.require_room(db, user, room_id, storage=False)
    if not categories.folder_schema_ready(db):
        raise HTTPException(503, '讨论名称配置尚未就绪')
    row = db.query(ChatSessionCategory).filter_by(id=room_id).with_for_update().first()
    if row is not None and row.revision != payload.revision:
        raise HTTPException(409, '讨论名称已被其他人修改，请重新加载后重试')
    parent_key = room.get('parent_key', service.RESOURCE_ROOT)
    name = categories.validate_name(db, payload.name, room_id, parent_key)
    if row is None:
        row = ChatSessionCategory(id=room_id, name=name, updated_by=user.id)
        db.add(row)
        from sqlalchemy.exc import IntegrityError
        try:
            db.flush()
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(409, '讨论名称已被其他人修改，请重新加载后重试') from error
        db.add(ChatSessionCategoryFolder(category_id=room_id, parent_key=service.RESOURCE_ROOT))
    else:
        row.name = name
        row.revision += 1
        row.updated_by, row.updated_at = user.id, category_now()
    categories.commit(db)
    return dict(categories.serialize(row), parent_key=parent_key)


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=10000)
    client_message_id: UUID
    reply_to_id: int | None = Field(default=None, ge=1)
    mentioned_user_ids: list[UUID] = Field(default_factory=list,max_length=20)
    mention_all: bool = False

    @model_validator(mode='before')
    @classmethod
    def discard_legacy_display_state(cls, value):
        # 旧页面会把 @ 候选人的显示资料放进请求；它不能决定实际收件人。
        if isinstance(value, dict) and 'selected_users' in value:
            return {key: item for key, item in value.items() if key != 'selected_users'}
        return value


class PreferenceWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pinned: bool | None = None
    starred: bool | None = None
    mark_read: bool = False
    read_message_id: int | None = Field(default=None, ge=1)


@router.put('/{room_id}/message-actions/{message_id}/{action}')
@router.delete('/{room_id}/message-actions/{message_id}/{action}')
def message_action(room_id: UUID, message_id: int, action: str, request: Request, db=Depends(get_db), user=Depends(actor)):
    if action not in ('favorite','acknowledgement'):
        raise HTTPException(404,'操作不存在')
    from discussion_message_actions import set_action
    return set_action(db,user,room_id,message_id,action,request.method == 'PUT')


@router.get('/{room_id}/group')
def group(room_id: UUID, db=Depends(get_db), user=Depends(actor)):
    from discussion_mentions import group
    return group(db,user,room_id)


@router.get('/{room_id}/messages')
def messages(room_id: UUID, before: int | None = Query(None, ge=1), after: int | None = Query(None, ge=1),
             limit: int = Query(50, ge=1, le=100), keyword: str = Query('', max_length=200), favorites_only: bool = False, db=Depends(get_db), user=Depends(actor)):
    if before is not None and after is not None:
        raise HTTPException(422, '不能同时指定向前和向后翻页')
    return service.messages(db, user, room_id, before, after, limit, keyword, favorites_only)


@router.post('/{room_id}/messages', status_code=201)
def send(room_id: UUID, payload: MessageCreate, db=Depends(get_db), user=Depends(actor)):
    return service.send(db, user, room_id, payload)


@router.put('/{room_id}/preferences')
def preferences(room_id: UUID, payload: PreferenceWrite, db=Depends(get_db), user=Depends(actor)):
    return service.preferences(db, user, room_id, payload)


@router.put('/{room_id}/messages/{message_id}/recall')
def recall(room_id: UUID, message_id: int, db=Depends(get_db), user=Depends(actor)):
    service.require_room(db, user, room_id)
    row = db.query(service.Message).filter_by(id=message_id, room_id=room_id).with_for_update().first()
    if not row:
        raise HTTPException(404, '消息不存在')
    if row.recalled_at:
        if row.sender_id != user.id:
            raise HTTPException(403, '不能撤回他人的消息')
        return service.serialize(db, row, user)
    if not service.serialize(db, row, user)['can_recall']:
        raise HTTPException(403, '只能撤回本人一小时内发送的消息')
    from chat_message_notifications import settle_notifications
    settle_notifications(db, 'discussion', room_id, message=row)
    row.recalled_at = service.category_now()
    db.commit(); service.publish(db)
    return service.serialize(db, row, user)
