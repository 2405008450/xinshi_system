"""按标注订单独立维护的客户进度。"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from annotation_progress_time import business_now
from models import Base


class AnnotationCustomerProgress(Base):
    __tablename__ = "annotation_customer_progress"
    __table_args__ = (
        CheckConstraint("length(trim(change_note)) BETWEEN 1 AND 10000", name="ck_annotation_customer_progress_note"),
        Index("ix_annotation_customer_progress_timeline", "project_id", text("effective_on DESC"), text("changed_at DESC"), text("id DESC")),
        Index("ix_annotation_customer_progress_recent", text("changed_at DESC"), text("id DESC")),
        Index("ix_annotation_customer_progress_search", "change_note", postgresql_using="gin", postgresql_ops={"change_note": "gin_trgm_ops"}),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("annotation_project.id", ondelete="CASCADE"), nullable=False)
    change_note: Mapped[str] = mapped_column(Text, nullable=False)
    effective_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=business_now, server_default=text("CURRENT_TIMESTAMP"))
    changed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=business_now, server_default=text("CURRENT_TIMESTAMP"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("app_user.id", ondelete="SET NULL"))
