"""资源开拓：记录、跟进历史、每日工作与共享配置。"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import mapped_column
from models import Base


class DevelopmentOption(Base):
    __tablename__ = "resource_development_option"
    __table_args__ = (UniqueConstraint("kind", "name"),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    kind = mapped_column(String(20), nullable=False)
    category = mapped_column(String(20), nullable=False, default="")
    name = mapped_column(String(100), nullable=False)
    code = mapped_column(String(30), unique=True)
    description = mapped_column(Text, nullable=False, default="")
    revision = mapped_column(Integer, nullable=False, default=1)


class DevelopmentCounter(Base):
    __tablename__ = "resource_development_counter"
    platform_id = mapped_column(Uuid, ForeignKey("resource_development_option.id"), primary_key=True)
    work_date = mapped_column(Date, primary_key=True)
    value = mapped_column(Integer, nullable=False, default=0)


class DevelopmentRecord(Base):
    __tablename__ = "resource_development_record"
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    greeting_no = mapped_column(String(80), nullable=False, unique=True)
    platform_id = mapped_column(Uuid, ForeignKey("resource_development_option.id"), nullable=False, index=True)
    work_date = mapped_column(Date, nullable=False, index=True)
    owner_id = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False, index=True)
    full_name = mapped_column(String(255), nullable=False)
    account_id = mapped_column(Uuid, ForeignKey("resource_development_option.id"))
    phone = mapped_column(String(100), nullable=False, default="")
    wechat = mapped_column(String(100), nullable=False, default="")
    wechat_status = mapped_column(String(100), nullable=False, default="未处理")
    enterprise_status = mapped_column(String(100), nullable=False, default="未处理")
    follow_up = mapped_column(Text, nullable=False, default="")
    remarks = mapped_column(Text, nullable=False, default="")
    person_id = mapped_column(Uuid, ForeignKey("resource_person.id", ondelete="SET NULL"))
    # 仅由受控历史导入设置，普通表单不得更改。
    historical_only = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    historical_markers = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    duplicate_note = mapped_column(Text, nullable=False, default="")
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    updated_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at = mapped_column(DateTime, nullable=False, default=datetime.now, index=True)
    revision = mapped_column(Integer, nullable=False, default=1)


class DevelopmentLanguage(Base):
    __tablename__ = "resource_development_language"
    record_id = mapped_column(Uuid, ForeignKey("resource_development_record.id", ondelete="CASCADE"), primary_key=True)
    language_id = mapped_column(Uuid, ForeignKey("interpretation_language.id"), primary_key=True)


class DevelopmentAction(Base):
    __tablename__ = "resource_development_action"
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    record_id = mapped_column(Uuid, ForeignKey("resource_development_record.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = mapped_column(String(20), nullable=False)
    status = mapped_column(String(100), nullable=False)
    request_number = mapped_column(Integer, nullable=False, default=0)
    action_date = mapped_column(Date, nullable=False)
    operator_id = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    account_id = mapped_column(Uuid, ForeignKey("resource_development_option.id"))
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    updated_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at = mapped_column(DateTime, nullable=False, default=datetime.now)


class DevelopmentWork(Base):
    __tablename__ = "resource_development_work"
    __table_args__ = (UniqueConstraint("work_date", "owner_id"),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    work_date = mapped_column(Date, nullable=False, index=True)
    owner_id = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False, index=True)
    periods = mapped_column(JSON, nullable=False, default=list)
    deduction = mapped_column(Integer, nullable=False, default=0)
    duration_minutes = mapped_column(Integer, nullable=False, default=0)
    completed = mapped_column(Boolean)
    explanation = mapped_column(Text, nullable=False, default="")
    revision = mapped_column(Integer, nullable=False, default=1)
    updated_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)


class DevelopmentScreenshot(Base):
    __tablename__ = "resource_development_screenshot"
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    work_id = mapped_column(Uuid, ForeignKey("resource_development_work.id", ondelete="CASCADE"), nullable=False, index=True)
    name = mapped_column(String(255), nullable=False)
    content_type = mapped_column(String(50), nullable=False)
    content = mapped_column(LargeBinary, nullable=False)
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False, default=datetime.now)


class DevelopmentAudit(Base):
    __tablename__ = "resource_development_audit"
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    entity_id = mapped_column(Uuid, nullable=False, index=True)
    entity_type = mapped_column(String(30), nullable=False)
    actor_id = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    action = mapped_column(String(30), nullable=False)
    before = mapped_column(JSON, nullable=False, default=dict)
    after = mapped_column(JSON, nullable=False, default=dict)
    created_at = mapped_column(DateTime, nullable=False, default=datetime.now)


class DevelopmentFriendDaily(Base):
    """群聊渠道每日新增量；applied 保留上次同步概览的稳定单元格。"""
    __tablename__ = "resource_development_friend_daily"
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    work_date = mapped_column(Date, nullable=False, unique=True, index=True)
    rows = mapped_column(JSON, nullable=False, default=list)
    applied = mapped_column(JSON, nullable=False, default=list)
    revision = mapped_column(Integer, nullable=False, default=1)
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    updated_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at = mapped_column(DateTime, nullable=False, default=datetime.now)
