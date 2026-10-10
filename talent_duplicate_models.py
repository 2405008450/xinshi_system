"""同名核重审计；完整快照只允许超级管理员访问。"""
import uuid
from sqlalchemy import DateTime, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class TalentDuplicateOperation(Base):
    __tablename__ = "talent_duplicate_operation"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    name_key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    person_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    actor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    decisions: Mapped[dict] = mapped_column(JSON, nullable=False)
    before_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    after_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    comparison_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    undone_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    undone_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
