import hashlib
import hmac
import json
import re
from datetime import timedelta
from uuid import UUID, uuid4
from urllib.parse import unquote
from fastapi import HTTPException
from sqlalchemy import inspect
from editor_screenshot_models import EditorScreenshot as Image, EditorScreenshotBlob as Blob, EditorScreenshotGrant as Grant
from chat_time import now, api_time

REFERENCE_RE=re.compile(r'screenshot://([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})')
SIGNED_REFERENCE_RE=re.compile(REFERENCE_RE.pattern+r'#([0-9a-fA-F]{64})')


def signed_reference(image_id):
    from routers.auth import SECRET_KEY
    uid=UUID(str(image_id))
    signature=hmac.new(SECRET_KEY.encode(),b'editor-screenshot-reference:'+uid.bytes,hashlib.sha256).hexdigest()
    return f'screenshot://{uid}#{signature}'


def valid_references(value):
    if isinstance(value,bytes):value=value.decode('utf-8',errors='ignore')
    if not isinstance(value,str):value=json.dumps(value,ensure_ascii=False,default=str)
    return {UUID(uid) for uid,signature in SIGNED_REFERENCE_RE.findall(value) if hmac.compare_digest(signed_reference(uid).split('#')[1],signature.lower())}


def references(value):
    if isinstance(value,bytes):value=value.decode('utf-8',errors='ignore')
    if not isinstance(value,str):value=json.dumps(value,ensure_ascii=False,default=str)
    return {UUID(match) for match in REFERENCE_RE.findall(value)}


def request_references(value):
    text=value.decode('utf-8',errors='ignore') if isinstance(value,bytes) else str(value)
    for _ in range(3):
        text=unquote(text).replace('\\/','/')
        text=re.sub(r'\\u([0-9a-fA-F]{4})',lambda match:chr(int(match[1],16)),text)
    return references(text)


def ready(db):
    inspector=inspect(db.connection())
    return all(inspector.has_table(name) for name in (Image.__tablename__,Blob.__tablename__,Grant.__tablename__))


def require_ready(db):
    if not ready(db):raise HTTPException(503,'统一截图功能尚未完成数据库初始化')


def permitted_ids(db,user_id,ids,tokens=()):
    ids=set(ids)
    if not ids:return set()
    require_ready(db)
    permitted={uid for uid, in db.query(Image.id).filter(Image.id.in_(ids),Image.uploaded_by==user_id)}
    valid=[]
    for token in tokens:
        try:valid.append(UUID(str(token)))
        except ValueError:continue
    if valid:
        for grant in db.query(Grant).filter(Grant.id.in_(valid),Grant.user_id==user_id,Grant.expires_at>now()):
            permitted.update(UUID(uid) for uid in grant.image_ids)
    return ids&permitted


def grant(db,user_id,ids):
    # 只有经过业务接口授权、实际返回的记录才会生成读取授权；写入前会校验引用归属。
    row=Grant(id=uuid4(),user_id=user_id,image_ids=sorted(str(uid) for uid in ids),expires_at=now()+timedelta(minutes=10))
    db.add(row);db.commit();return str(row.id),int(api_time(row.expires_at).timestamp())


def save_image(db,user_id,content,content_type,retention='business'):
    require_ready(db)
    if retention not in {'business','chat'}:raise ValueError('截图保留类型无效')
    from mail_inline_image_service import normalize_uploaded_image
    data,mime,*_=normalize_uploaded_image(content,content_type)
    digest=hashlib.sha256(data).hexdigest()
    dialect=db.get_bind().dialect.name
    if dialect in {'postgresql','sqlite'}:
        if dialect=='postgresql':from sqlalchemy.dialects.postgresql import insert
        else:from sqlalchemy.dialects.sqlite import insert
        db.execute(insert(Blob).values(sha256=digest,content=data,content_type=mime,byte_size=len(data)).on_conflict_do_nothing())
    elif not db.get(Blob,digest):db.add(Blob(sha256=digest,content=data,content_type=mime,byte_size=len(data)))
    row=Image(id=uuid4(),blob_sha256=digest,uploaded_by=user_id,retention_kind=retention,expires_at=now()+timedelta(days=30) if retention=='chat' else None)
    db.add(row);db.commit();return {'id':str(row.id),'reference':signed_reference(row.id),'size':len(data),'contentType':mime}


def check_chat_reference(db,user,image_id,message_id,kind=None):
    from models import ChatProjectMessage
    # 复用逐条消息的现有参与权限，不允许通过截图接口绕过会话隔离。
    if kind=='discussion':
        from discussion_chat_models import DiscussionMessage
        try:message=db.get(DiscussionMessage,int(message_id))
        except ValueError:message=None
    else:
        try:message=db.get(ChatProjectMessage,UUID(str(message_id)))
        except ValueError:message=None
    if message is None:raise HTTPException(404,'会话消息不存在')
    from chat_access_service import require_member
    if kind=='discussion':project_id=message.room_id
    else:
        kind='annotation' if message.annotation_project_id else 'direct' if message.direct_conversation_id else 'translation'
        project_id=message.annotation_project_id or message.direct_conversation_id or message.project_id
    require_member(db,kind,project_id,user)
    if message.recalled_at or image_id not in valid_references(message.content):raise HTTPException(404,'截图不属于该消息')
    if api_time(message.created_at)<=now()-timedelta(days=30):raise HTTPException(410,'聊天截图已超过30天保留期，文字记录仍保留')


def clean_expired_grants(db):
    if ready(db):db.query(Grant).filter(Grant.expires_at<now()).delete(synchronize_session=False);db.commit()


def promote_business_references(db,ids):
    if ids:
        db.query(Image).filter(Image.id.in_(ids),Image.blob_sha256.isnot(None),(Image.expires_at.is_(None))|(Image.expires_at>now())).update({Image.retention_kind:'business',Image.expires_at:None},synchronize_session=False)


def cleanup(db):
    """只清理过期聊天图片字节与短期授权，不删除消息和业务图片。"""
    if not ready(db):return
    db.query(Image).filter(Image.retention_kind=='chat',Image.expires_at<=now(),Image.blob_sha256.isnot(None)).update({Image.blob_sha256:None},synchronize_session='fetch')
    db.query(Blob).filter(~Blob.sha256.in_(db.query(Image.blob_sha256).filter(Image.blob_sha256.isnot(None)))).delete(synchronize_session=False)
    db.query(Grant).filter(Grant.expires_at<now()).delete(synchronize_session=False)
    db.commit()
