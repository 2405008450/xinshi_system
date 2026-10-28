import os
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from pywebpush import webpush, WebPushException
from database import get_db
from models import AppUser, PushSubscription
from routers.auth import get_current_user # 使用你项目现有的获取当前用户依赖
from pydantic import BaseModel

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
    # 避免重复订阅
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


import uuid
from sqlalchemy import text

def send_push_to_user(db: Session, user_id: str, title: str, body: str, url: str = "/"):
    """供聊天发送消息时调用的核心推送函数"""
    # 强制将 user_id 转为字符串或者 uuid 对象，防止类型不匹配导致查不到数据
    try:
        target_id = uuid.UUID(str(user_id))
    except ValueError:
        target_id = user_id

    # 查询该用户的订阅信息
    subs = db.query(PushSubscription).filter(PushSubscription.user_id == target_id).all()
    if not subs:
        print(f"⚠️ 用户 {target_id} 没有订阅推送（数据库里找不到），跳过发送")
        return

    vapid_private = os.getenv("VAPID_PRIVATE_KEY")
    vapid_claims = {"sub": os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")}

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url
    })

    for sub in subs:
        try:
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
            print(f"✅ 成功向 {target_id} 发送系统级推送")
        except WebPushException as ex:
            # 如果推送失败（比如用户清除了浏览器缓存），就删掉这个无效订阅
            print(f"❌ 推送失败: {type(ex).__name__}: {ex}")

            response = ex.response
            if response is not None:
                print("HTTP 状态码:", response.status_code)
                print("响应头:")
                for key, value in response.headers.items():
                    if key.lower().startswith("x-wns-") or key.lower() in (
                            "content-type",
                            "www-authenticate",
                            "date",
                    ):
                        print(f"  {key}: {value}")

                print("响应正文:", repr(response.text[:2000]))
            else:
                print("没有收到 HTTP 响应")