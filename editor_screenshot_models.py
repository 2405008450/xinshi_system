"""通用编辑截图：压缩内容去重、永久引用和短期读取授权。"""
from uuid import uuid4
from sqlalchemy import String, LargeBinary, Integer, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.orm import mapped_column
from models import Base
from chat_time import now


class EditorScreenshotBlob(Base):
    __tablename__='editor_screenshot_blob'
    sha256=mapped_column(String(64),primary_key=True)
    content=mapped_column(LargeBinary,nullable=False,deferred=True)
    content_type=mapped_column(String(40),nullable=False)
    byte_size=mapped_column(Integer,nullable=False)


class EditorScreenshot(Base):
    __tablename__='editor_screenshot'
    id=mapped_column(Uuid,primary_key=True,default=uuid4)
    blob_sha256=mapped_column(String(64),ForeignKey('editor_screenshot_blob.sha256'),nullable=True,index=True)
    uploaded_by=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False,index=True)
    created_at=mapped_column(DateTime(timezone=True),nullable=False,default=now)
    retention_kind=mapped_column(String(16),nullable=False,default='business')
    expires_at=mapped_column(DateTime(timezone=True),index=True)


class EditorScreenshotGrant(Base):
    __tablename__='editor_screenshot_grant'
    id=mapped_column(Uuid,primary_key=True,default=uuid4)
    user_id=mapped_column(Uuid,ForeignKey('app_user.id',ondelete='CASCADE'),nullable=False,index=True)
    image_ids=mapped_column(JSON,nullable=False)
    expires_at=mapped_column(DateTime(timezone=True),nullable=False,index=True)
