from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from crud import (
    count_unread_notifications,
    get_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)
import asyncio

from database import SessionLocal, get_db
from models import AppUser
from notification_ws import notification_manager
from routers.auth import get_current_user, get_user_from_token_value
from schemas import NotificationResponse
from notification_channels import NotificationChannel

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=list[NotificationResponse])
def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    channel: NotificationChannel = 'all',
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
    )


@router.get("/unread-count")
def unread_count(
    channel: NotificationChannel = 'all',
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return {"count": count_unread_notifications(db, current_user.id, channel=channel)}


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
async def notifications_ws(websocket: WebSocket, token: str = Query(default="")):
    if not token:
        await websocket.close(code=1008)
        return

    user_id = None
    try:
        snapshot = await run_in_threadpool(_socket_snapshot, token)
        if snapshot is None:
            await websocket.close(code=1008)
            return
        user_id, unread, business_unread = snapshot

        await notification_manager.connect(user_id, websocket)
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
            if message is None:
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
