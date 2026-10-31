import os
import json
import uuid
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from pywebpush import webpush, WebPushException
from database import get_db
from models import AppUser, PushSubscription
from routers.auth import get_current_user

router = APIRouter(prefix="/push", tags=["Push"])


class SubReq(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


@router.get("/public_key")
def get_public_key():
    return {"publicKey": os.getenv("VAPID_PUBLIC_KEY")}


@router.post("/subscribe")
def subscribe(req: SubReq, db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user)):
    sub = db.query(PushSubscription).filter_by(endpoint=req.endpoint).first()
    if not sub:
        sub = PushSubscription(
            user_id=current_user.id,
            endpoint=req.endpoint,
            p256dh=req.p256dh,
            auth=req.auth
        )
        db.add(sub)
    else:
        sub.user_id = current_user.id
    db.commit()
    return {"status": "ok"}


def send_push_to_user(db: Session, user_id: str, title: str, body: str, url: str = "/"):
    """供聊天发送消息时调用的核心推送函数"""
    try:
        target_id = uuid.UUID(str(user_id))
    except ValueError:
        target_id = user_id

    subs = db.query(PushSubscription).filter(PushSubscription.user_id == target_id).all()
    if not subs:
        print(f"⚠️ 用户 {target_id} 没有订阅推送（数据库里找不到），跳过发送")
        return

    vapid_private = os.getenv("VAPID_PRIVATE_KEY")
    vapid_subject = os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url
    })

    for sub in subs:
        try:
            # 👇 核心修复：动态提取 endpoint 的域名作为 aud 字段
            parsed = urlparse(sub.endpoint)
            aud = f"{parsed.scheme}://{parsed.netloc}"
            vapid_claims = {
                "sub": vapid_subject,
                "aud": aud  # 必须包含此字段，否则 FCM(安卓) 会报 403
            }

            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth
                    }
                },
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims=vapid_claims,
                content_encoding="aes128gcm",
                ttl=600
            )
            print(f"✅ 成功向 {target_id} 发送系统级推送 -> 端点: {aud}")

        except WebPushException as ex:
            print(f"❌ 推送失败: {type(ex).__name__}: {ex}")
            response = ex.response

            # 👇 如果端点已失效（410或404），直接从数据库删除这个订阅
            if response is not None and response.status_code in [404, 410]:
                print(f"🗑️ 发现失效端点 ({response.status_code})，已自动从数据库清理。")
                db.delete(sub)
                db.commit()