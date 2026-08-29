import datetime
import uuid

from sqlalchemy import BigInteger, DateTime, Index, Integer, PrimaryKeyConstraint, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from models import Base


class LoginThrottleState(Base):
    """登录限流状态，只保存账号/IP 的不可逆 HMAC 指纹。"""

    __tablename__ = "login_throttle_state"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="login_throttle_state_pkey"),
        UniqueConstraint("dimension", "key_hash", name="uq_login_throttle_state_dimension_key"),
        Index("ix_login_throttle_state_blocked_until", "blocked_until"),
        Index("ix_login_throttle_state_updated_at", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dimension: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_timestamps: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    block_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    blocked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    last_failed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LoginSecurityEvent(Base):
    """登录安全审计，不记录口令、原始账号或原始来源地址。"""

    __tablename__ = "login_security_event"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="login_security_event_pkey"),
        Index("ix_login_security_event_created_at", "created_at"),
        Index("ix_login_security_event_account_hash", "account_hash"),
        Index("ix_login_security_event_source_hash", "source_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    account_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    account_failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    source_failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    blocked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RevokedAccessToken(Base):
    """已主动撤销的访问令牌，仅保存 JTI 摘要，不落库原始令牌。"""

    __tablename__ = "revoked_access_token"
    __table_args__ = (
        PrimaryKeyConstraint("jti_hash", name="revoked_access_token_pkey"),
        Index("ix_revoked_access_token_expires_at", "expires_at"),
    )

    jti_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
