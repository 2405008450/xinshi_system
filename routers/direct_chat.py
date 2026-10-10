"""内部双方私聊接口。"""
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models import AppUser, ChatDirectMember, ChatProjectMessage
from routers.auth import get_current_user
from routers.annotation_chat import ReadRequest, RefreshRequest
from schemas import AnnotationProjectChatMessageCreate
from chat_common_handlers import chat_timeline, upload_chat_file
from chat_history_search import search_chat_history
from chat_time import api_time
import direct_chat_service as service
from chat_schema import require_phase_one

router = APIRouter(prefix='/chat/direct', tags=['direct_chat'], dependencies=[Depends(require_phase_one)])


class ConversationRequest(BaseModel):
    user_id: UUID


@router.post('/conversations')
def open_conversation(payload: ConversationRequest, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return service.open_conversation(db, user, payload.user_id)


@router.get('/{project_id}/group')
def group(project_id: UUID, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    row = service.require_project(db, project_id, user)
    members = [db.get(AppUser, uid) for uid in (row.user_low_id, row.user_high_id)]
    return {'members': [{'id': u.id, 'name': u.full_name or u.username} for u in members],
        'eligible_users': [], 'following': True, 'last_read_sequence': db.get(ChatDirectMember, (project_id, user.id)).last_read_sequence}


@router.get('/{project_id}/timeline')
def timeline(project_id: UUID, before: int | None = None, after: int | None = None, around: UUID | None = None,
    limit: int = Query(30, ge=1, le=100), keyword: str = '', sender_user_id: UUID | None = None,
    favorites_only: bool = False, date_from: str | None = None, date_to: str | None = None,
    db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return chat_timeline(service, project_id, before, after, around, limit, keyword, sender_user_id, favorites_only, date_from, date_to, db, user)


@router.post('/{project_id}/messages', status_code=201)
def send(project_id: UUID, payload: AnnotationProjectChatMessageCreate, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return service.serialize_many(db, [service.send_message(db, project_id, user, payload)], user)[0]


@router.post('/{project_id}/refresh')
def refresh(project_id: UUID, payload: RefreshRequest, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    service.require_project(db, project_id, user)
    return {'items': service.serialize_many(db, service.message_query(db, project_id).filter(ChatProjectMessage.id.in_(payload.message_ids)).all(), user)}


@router.get('/{project_id}/sent/{client_message_id}')
def sent(project_id: UUID, client_message_id: UUID, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    service.require_project(db, project_id, user)
    row = service.message_query(db, project_id).filter_by(sender_user_id=user.id, client_message_id=client_message_id).first()
    return {'message': service.serialize_many(db, [row], user)[0] if row else None}


@router.put('/{project_id}/read')
def read(project_id: UUID, payload: ReadRequest, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    service.require_project(db, project_id, user, lock=True)
    message = service.message_query(db, project_id).filter_by(id=payload.message_id).first()
    if not message:
        raise HTTPException(404, '消息不存在')
    member = db.get(ChatDirectMember, (project_id, user.id))
    member.last_read_sequence = max(member.last_read_sequence, message.sequence_no)
    db.commit(); service.publish(db, project_id, 'state')
    return {'last_read_sequence': member.last_read_sequence}


@router.post('/{project_id}/messages/{message_id}/recall')
def recall(project_id: UUID, message_id: UUID, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return service.serialize_many(db, [service.recall_message(db, project_id, message_id, user)], user)[0]


@router.get('/{project_id}/history')
def history(project_id: UUID, kind: str = Query('all', pattern='^(all|image|link|file)$'), keyword: str = '',
    sender_user_id: UUID | None = None, favorites_only: bool = False, date_from: str | None = None,
    date_to: str | None = None, cursor: str | None = None, limit: int = Query(30, ge=1, le=50),
    db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    service.require_project(db, project_id, user)
    try:
        return api_time(search_chat_history(db, project_type='direct', project_id=project_id, user_id=user.id,
            kind=kind, keyword=keyword, sender_user_id=sender_user_id, favorites_only=favorites_only,
            date_from=datetime.fromisoformat(date_from) if date_from else None,
            date_to=datetime.fromisoformat(date_to) if date_to else None, cursor=cursor, limit=limit))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post('/{project_id}/files', status_code=201)
async def upload(project_id: UUID, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return await upload_chat_file(service, 'direct', project_id, request, file, db, user)


@router.get('/{project_id}/files/{attachment_id}')
async def download(project_id: UUID, attachment_id: UUID, request: Request, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    service.require_project(db, project_id, user)
    attachment = service.authorize_attachment(db, attachment_id, user)
    if attachment.direct_conversation_id != project_id:
        raise HTTPException(404, '附件不属于当前会话')
    from chat_attachment_storage import remote_attachment_url, read_remote_attachment
    from routers.project_chat import get_chat_upload_dir
    remote = remote_attachment_url()
    if remote:
        return await read_remote_attachment(remote, attachment_id, request.headers.get('authorization'), request.headers.get('x-chat-attachment-forwarded'), allow_files=True)
    path = get_chat_upload_dir() / attachment.storage_name
    if not path.is_file():
        raise HTTPException(404, '文件不存在')
    return FileResponse(path, filename=attachment.original_name, media_type=attachment.content_type,
        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
