"""推荐拓展：奖励台账、分类图片及独立操作历史。"""
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, JSON, LargeBinary, Numeric, String, Text, Uuid
from sqlalchemy.orm import mapped_column
from models import Base


class ReferralRecord(Base):
    __tablename__ = "referral_development_record"
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    work_date = mapped_column(Date, nullable=False, index=True)
    full_name = mapped_column(String(255), nullable=False)
    wechat = mapped_column(String(100), nullable=False, default="")
    pull_description = mapped_column(Text, nullable=False, default="")
    moments_description = mapped_column(Text, nullable=False, default="")
    groups_description = mapped_column(Text, nullable=False, default="")
    amount = mapped_column(Numeric(12, 2), nullable=False)
    payment_status = mapped_column(String(20), nullable=False, default="unpaid", index=True)
    payment_date = mapped_column(Date)
    remarks = mapped_column(Text, nullable=False, default="")
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False, index=True)
    updated_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False)
    updated_at = mapped_column(DateTime, nullable=False)
    revision = mapped_column(Integer, nullable=False, default=1)


class ReferralImage(Base):
    __tablename__ = "referral_development_image"
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    record_id = mapped_column(Uuid, ForeignKey("referral_development_record.id", ondelete="CASCADE"), nullable=False, index=True)
    category = mapped_column(String(20), nullable=False)
    name = mapped_column(String(255), nullable=False)
    content_type = mapped_column(String(30), nullable=False)
    content = mapped_column(LargeBinary, nullable=False)
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False)


class ReferralAudit(Base):
    __tablename__ = "referral_development_audit"
    __table_args__ = (Index("ix_referral_audit_record_time", "record_id", "created_at", "id"),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    # 删除台账后仍保留审计快照，不使用级联外键。
    record_id = mapped_column(Uuid, nullable=False)
    action = mapped_column(String(30), nullable=False)
    actor_id = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False)
    before = mapped_column(JSON, nullable=False, default=dict)
    after = mapped_column(JSON, nullable=False, default=dict)
