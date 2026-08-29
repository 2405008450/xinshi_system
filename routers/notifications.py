from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from crud import (
    count_unread_notifications,
    get_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)
from database import SessionLocal, get_db
from models import AppUser
from notification_ws import notification_manager
from routers.auth import get_current_user, get_user_from_token_value
from schemas import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=list[NotificationResponse])
def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return get_notifications(
        db,
        recipient_user_id=current_user.id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
    )


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return {"count": count_unread_notifications(db, current_user.id)}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def read_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    notification = mark_notification_read(db, notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification


@router.post("/read-all")
def read_all_notifications(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    updated = mark_all_notifications_read(db, current_user.id)
    return {"updated": updated}


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, token: str = Query(default="")):
    if not token:
        await websocket.close(code=1008)
        return

    db = SessionLocal()
    db_released = False
    user_id = None
    try:
        user = get_user_from_token_value(db, token)
        if user is None:
            await websocket.close(code=1008)
            return

        # SQLAlchemy 的首次查询会自动开启事务。WebSocket 连接可能持续数小时，
        # 因此只复制后续所需的标量值，并在进入收包循环前结束事务、归还连接。
        user_id = user.id
        unread = count_unread_notifications(db, user_id)
        db.rollback()
        db.close()
        db_released = True

        await notification_manager.connect(user_id, websocket)
        await websocket.send_json({"type": "snapshot", "unread_count": unread})

        while True:
            message = await websocket.receive_text()
            if message == 'ping':
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        if user_id is not None:
            notification_manager.disconnect(user_id, websocket)
    except Exception:
        if user_id is not None:
            notification_manager.disconnect(user_id, websocket)
        await websocket.close(code=1011)
    finally:
        if not db_released:
            db.rollback()
        db.close()
