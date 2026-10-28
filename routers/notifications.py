from uuid import UUID, uuid4
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from crud import (
    count_unread_notifications,
    count_notifications,
    get_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)
import asyncio

from database import SessionLocal, get_db
from models import AppUser
from notification_ws import notification_manager, connection_client_type
from routers.auth import get_current_user, get_user_from_token_value
from schemas import NotificationResponse
from notification_channels import NotificationChannel
from pagination_schemas import PageResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get('/page', response_model=PageResponse[NotificationResponse])
def notification_page(
    skip: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100),
    keyword: str | None = Query(None, max_length=500),
    read_status: Literal['all', 'read', 'unread'] = 'all',
    channel: NotificationChannel = 'all',
    notification_type: str | None = Query(None, max_length=100),
    notification_types: list[str] | None = Query(None, max_length=20),
    db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user),
):
    filters = dict(keyword=keyword, read_status=read_status, channel=channel,
                   notification_type=notification_type, notification_types=notification_types)
    return {'items': get_notifications(db, current_user.id, skip=skip, limit=limit, **filters),
            'total': count_notifications(db, current_user.id, **filters)}


@router.get("/", response_model=list[NotificationResponse])
def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    channel: NotificationChannel = 'all',
    notification_type: str | None = Query(None, max_length=100),
    notification_types: list[str] | None = Query(None, max_length=20),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return get_notifications(
        db,
        recipient_user_id=current_user.id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
        channel=channel,
        notification_type=notification_type,
        notification_types=notification_types,
    )


@router.get("/unread-count")
def unread_count(
    channel: NotificationChannel = 'all',
    notification_type: str | None = Query(None, max_length=100),
    notification_types: list[str] | None = Query(None, max_length=20),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return {"count": count_unread_notifications(db, current_user.id, channel=channel, notification_type=notification_type,notification_types=notification_types)}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def read_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    from models import AppNotification
    from notification_channels import filter_notification_visibility
    if not filter_notification_visibility(db.query(AppNotification.id).filter(AppNotification.id == notification_id, AppNotification.recipient_user_id == current_user.id), AppNotification, db, current_user.id).first():
        raise HTTPException(404, '通知不存在')
    notification = mark_notification_read(db, notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")
    return notification


@router.post("/read-all")
def read_all_notifications(
    channel: NotificationChannel = 'all',
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    updated = mark_all_notifications_read(db, current_user.id, channel=channel)
    return {"updated": updated}


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, token: str = Query(default=""), client_type: str = Query(default='', max_length=16)):
    if not token:
        await websocket.close(code=1008)
        return

    user_id = None
    presence_id, presence_sequence = uuid4(), 0
    desktop = connection_client_type(websocket, client_type) == 'desktop'
    try:
        snapshot = await run_in_threadpool(_socket_snapshot, token)
        if snapshot is None:
            await websocket.close(code=1008)
            return
        user_id, unread, business_unread = snapshot

        await notification_manager.connect(user_id, websocket, client_type)
        if desktop:
            presence_sequence += 1
            await run_in_threadpool(_publish_socket_presence, user_id, presence_id, presence_sequence, True)
        await websocket.send_json({"type": "snapshot", "unread_count": unread, "business_unread_count": business_unread})

        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=25)
            except asyncio.TimeoutError:
                message = None
            # 即使客户端不发送心跳，也定期重新鉴权，关闭改密后已失效的连接。
            valid = await run_in_threadpool(_socket_token_valid, token)
            if not valid:
                notification_manager.disconnect(user_id, websocket)
                await websocket.close(code=1008)
                return
            # 没有业务文本不代表离线；Uvicorn 协议层 ping/pong 独立于浏览器 JS
            # 定时器，断网会触发 receive_text 的断开事件。仍连接时续期共享租约。
            notification_manager.touch(user_id, websocket)
            if desktop:
                presence_sequence += 1
                await run_in_threadpool(_publish_socket_presence, user_id, presence_id, presence_sequence, True)
            if message is None:
                await websocket.send_json({'type': 'ping'})
                continue
            if message == 'ping':
                await websocket.send_json({"type": "pong"})
            else:
                import json
                try:
                    payload = json.loads(message)
                    if payload.get('type') == 'annotation_chat_watch':
                        project_id = UUID(payload.get('projectId', ''))
                        await run_in_threadpool(_authorize_annotation_watch, token, project_id)
                        notification_manager.watch_annotation(user_id, websocket, project_id, bool(payload.get('active')))
                except (ValueError, TypeError, HTTPException):
                    await websocket.send_json({'type': 'annotation_chat_watch_error'})
    except WebSocketDisconnect:
        if user_id is not None:
            notification_manager.disconnect(user_id, websocket)
    except Exception:
        if user_id is not None:
            notification_manager.disconnect(user_id, websocket)
        await websocket.close(code=1011)
    finally:
        if desktop and user_id is not None:
            notification_manager.disconnect(user_id, websocket)
            await run_in_threadpool(_publish_socket_presence, user_id, presence_id, presence_sequence + 1, False)


def _publish_socket_presence(user_id, client_id, sequence, active):
    # 兼容已有前端：服务端从已鉴权的电脑连接采集，不依赖新增 HTTP 心跳。
    from chat_presence_registry import record
    from sqlalchemy.exc import SQLAlchemyError
    try:
        with SessionLocal() as db:
            return record(db, user_id, client_id, sequence, active)
    except SQLAlchemyError:
        # 心跳存储失败不能影响聊天；当前进程仍保留真实连接，后续心跳重试。
        return False


def _socket_snapshot(token):
    # 整个同步事务在线程池内完成，关闭 Session 后才返回标量快照。
    # 不能在 WebSocket 事件循环上等待数据库连接，否则会阻塞 HTTP 响应及连接归还。
    with SessionLocal() as db:
        user = get_user_from_token_value(db, token)
        if user is None:
            return None
        user_id = user.id
        return (user_id, count_unread_notifications(db, user_id),
                count_unread_notifications(db, user_id, channel='business'))


def _socket_token_valid(token):
    with SessionLocal() as db:
        return get_user_from_token_value(db, token) is not None


def _authorize_annotation_watch(token, project_id):
    from annotation_chat_service import require_project
    with SessionLocal() as db:
        current = get_user_from_token_value(db, token)
        require_project(db, project_id, current)
