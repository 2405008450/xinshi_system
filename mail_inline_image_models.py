"""邮件正文内嵌图片及其业务绑定。"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, String, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class MailInlineImage(Base):
    __tablename__ = "mail_inline_image"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="mail_inline_image_pkey"),
        ForeignKeyConstraint(["uploaded_by"], ["app_user.id"], ondelete="CASCADE", name="fk_mail_inline_image_uploader"),
        Index("ix_mail_inline_image_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class MailInlineImageBinding(Base):
    __tablename__ = "mail_inline_image_binding"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="mail_inline_image_binding_pkey"),
        ForeignKeyConstraint(["image_id"], ["mail_inline_image.id"], ondelete="CASCADE", name="fk_mail_inline_image_binding_image"),
        UniqueConstraint("image_id", "scope_type", "scope_id", name="uq_mail_inline_image_binding_scope"),
        Index("ix_mail_inline_image_binding_scope", "scope_type", "scope_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    image_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
