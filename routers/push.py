"""浏览器推送订阅；未配置密钥或未迁移时不影响现有聊天。"""
import ipaddress
import json
import logging
import os
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from database import get_db
from models import AppUser, PushSubscription
from routers.auth import get_current_user

router = APIRouter(prefix='/push', tags=['Push'])
logger = logging.getLogger(__name__)


class EndpointRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=4096)

    @field_validator('endpoint')
    @classmethod
    def public_https_endpoint(cls, value):
        parsed = urlparse(value)
        host = parsed.hostname or ''
        if parsed.scheme != 'https' or not host or parsed.username or parsed.password or parsed.fragment:
            raise ValueError('推送端点必须为 HTTPS 地址')
        if host == 'localhost' or host.endswith(('.localhost', '.local')):
            raise ValueError('推送端点不能为本机地址')
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if '.' not in host:
                raise ValueError('推送端点必须为公网地址')
        else:
            if not address.is_global:
                raise ValueError('推送端点必须为公网地址')
        return value


class SubReq(EndpointRequest):
    p256dh: str = Field(min_length=1, max_length=255)
    auth: str = Field(min_length=1, max_length=255)


def configured():
    return bool(os.getenv('VAPID_PUBLIC_KEY') and os.getenv('VAPID_PRIVATE_KEY') and os.getenv('VAPID_SUBJECT'))


def schema_ready(db):
    return inspect(db.connection()).has_table(PushSubscription.__tablename__)


@router.get('/public_key')
def get_public_key():
    return {'publicKey': os.getenv('VAPID_PUBLIC_KEY') if configured() else None}


@router.post('/subscribe')
def subscribe(req: SubReq, db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user)):
    if not configured() or not schema_ready(db):
        raise HTTPException(503, '浏览器推送尚未完成配置或数据库迁移')
    sub = db.query(PushSubscription).filter_by(endpoint=req.endpoint).first()
    if sub is None:
        sub = PushSubscription(endpoint=req.endpoint)
        db.add(sub)
    sub.user_id = current_user.id
    sub.p256dh = req.p256dh
    sub.auth = req.auth
    db.commit()
    return {'status': 'ok'}


@router.post('/unsubscribe')
def unsubscribe(req: EndpointRequest, db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user)):
    if schema_ready(db):
        db.query(PushSubscription).filter_by(user_id=current_user.id, endpoint=req.endpoint).delete(synchronize_session=False)
        db.commit()
    return {'status': 'ok'}


def send_push_to_user(db, user_id, title, body, url='/'):
    if not configured():
        return
    try:
        from pywebpush import WebPushException, webpush
        if not schema_ready(db):
            return
        target = UUID(str(user_id))
        user = db.get(AppUser, target)
        if user is None or not user.is_active or user.is_deleted:
            return
        subscriptions = db.query(PushSubscription).filter_by(user_id=target).all()
        target_url = url if url.startswith('/') and not url.startswith('//') else '/workbench'
        payload = json.dumps({'title': title, 'body': body, 'url': target_url, 'userId': str(target)}, ensure_ascii=False)
        for sub in subscriptions:
            try:
                parsed = urlparse(EndpointRequest(endpoint=sub.endpoint).endpoint)
                webpush(subscription_info={'endpoint': sub.endpoint, 'keys': {'p256dh': sub.p256dh, 'auth': sub.auth}},
                        data=payload, vapid_private_key=os.environ['VAPID_PRIVATE_KEY'],
                        vapid_claims={'sub': os.environ['VAPID_SUBJECT'], 'aud': f'{parsed.scheme}://{parsed.netloc}'},
                        content_encoding='aes128gcm', ttl=600, timeout=5)
            except WebPushException as error:
                response = error.response
                if response is not None and response.status_code in (404, 410):
                    db.delete(sub)
                    db.commit()
                else:
                    logger.warning('浏览器推送暂未送达：%s', type(error).__name__)
            except Exception as error:
                logger.warning('浏览器推送暂未送达：%s', type(error).__name__)
    except Exception as error:
        logger.warning('浏览器推送暂不可用：%s', type(error).__name__)
