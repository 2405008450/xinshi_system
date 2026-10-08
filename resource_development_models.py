"""资源开拓：记录、跟进历史、每日工作与共享配置。"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, LargeBinary, String, Text, UniqueConstraint, Uuid
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
    purpose = mapped_column(Text, nullable=False, default="", server_default="")
    # 历史平台的创建信息未知，迁移时保留空值，不伪造创建时间。
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"))
    updated_by = mapped_column(Uuid, ForeignKey("app_user.id"))
    created_at = mapped_column(DateTime)
    updated_at = mapped_column(DateTime)


class DevelopmentChannelMember(Base):
    """平台人员分工；名单只记录责任，不参与访问权限判断。"""
    __tablename__ = "resource_development_channel_member"
    __table_args__ = (
        CheckConstraint("role IN ('maintainer', 'user')", name="ck_channel_member_role"),
        Index("ix_channel_member_user_role", "user_id", "role"),
    )
    platform_id = mapped_column(Uuid, ForeignKey("resource_development_option.id", ondelete="CASCADE"), primary_key=True)
    user_id = mapped_column(Uuid, ForeignKey("app_user.id"), primary_key=True)
    role = mapped_column(String(20), primary_key=True)


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
    friend_accounts = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    # 同步状态只用于当前展示、筛选；原始状态继续作为日报和业绩依据。
    contact_state = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    phone = mapped_column(String(100), nullable=False, default="")
    wechat = mapped_column(String(100), nullable=False, default="")
    xiaohongshu = mapped_column(String(100), nullable=False, default="", server_default="")
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


class DevelopmentFollowUp(Base):
    """纯文字跟进，只能追加；操作人和时间由服务端记录。"""
    __tablename__ = "resource_development_follow_up"
    __table_args__ = (Index("ix_resource_development_follow_up_record_time", "record_id", "created_at", "id"),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    record_id = mapped_column(Uuid, ForeignKey("resource_development_record.id", ondelete="CASCADE"), nullable=False)
    content = mapped_column(Text, nullable=False)
    operator_id = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False)


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


class DevelopmentArrangement(Base):
    """每日统筹；工时和日报仍使用独立的 DevelopmentWork。"""
    __tablename__ = "resource_development_arrangement"
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    work_date = mapped_column(Date, nullable=False, unique=True, index=True)
    remarks = mapped_column(Text, nullable=False, default="")
    revision = mapped_column(Integer, nullable=False, default=1)
    created_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    updated_by = mapped_column(Uuid, ForeignKey("app_user.id"), nullable=False)
    created_at = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at = mapped_column(DateTime, nullable=False, default=datetime.now)


class DevelopmentArrangementCell(Base):
    __tablename__ = "resource_development_arrangement_cell"
    __table_args__ = (UniqueConstraint("arrangement_id", "platform_id"),)
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    arrangement_id = mapped_column(Uuid, ForeignKey("resource_development_arrangement.id", ondelete="CASCADE"), nullable=False, index=True)
    platform_id = mapped_column(Uuid, ForeignKey("resource_development_option.id"), nullable=False)
    platform_name = mapped_column(String(100), nullable=False)
    owner_id = mapped_column(Uuid, ForeignKey("app_user.id"), index=True)
    owner_name = mapped_column(String(255), nullable=False, default="")
    # 名称快照由服务端生成，取消需求或改字典名称不会改写历史。
    targets = mapped_column(JSON, nullable=False, default=list)
    projects = mapped_column(JSON, nullable=False, default=list)
    remarks = mapped_column(Text, nullable=False, default="")
    completed = mapped_column(Boolean, nullable=False, default=False)
    completed_by = mapped_column(Uuid, ForeignKey("app_user.id"))
    completed_by_name = mapped_column(String(255), nullable=False, default="")
    completed_at = mapped_column(DateTime)
