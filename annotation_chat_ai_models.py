from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class AnnotationChatAnalysis(Base):
    __tablename__ = 'annotation_chat_analysis'
    __table_args__ = (
        UniqueConstraint('project_id', 'scheduled_on', name='uq_annotation_chat_ai_scheduled'),
        Index('ix_annotation_chat_ai_queue', 'state', 'created_at'),
        Index('ix_annotation_chat_ai_project', 'project_id', 'created_at'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey('annotation_project.id', ondelete='CASCADE'))
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey('app_user.id', ondelete='SET NULL'))
    scheduled_on: Mapped[date | None] = mapped_column(Date)
    period: Mapped[str] = mapped_column(String(16))
    range_start: Mapped[datetime | None] = mapped_column(DateTime)
    range_end: Mapped[datetime] = mapped_column(DateTime)
    auto_apply: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[str] = mapped_column(String(16), default='queued')
    error: Mapped[str | None] = mapped_column(String(500))
    import_error: Mapped[str | None] = mapped_column(String(500))
    results: Mapped[list] = mapped_column(JSON, default=list)
    imports: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
