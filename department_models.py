"""全系统共享部门目录。"""
import uuid
from sqlalchemy import String, Integer, JSON, DateTime, Uuid, Index, func, ForeignKey
from sqlalchemy.orm import mapped_column
from models import Base
from chat_time import now


class Department(Base):
    __tablename__ = 'system_department'
    id = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name = mapped_column(String(50), nullable=False, unique=True)
    __table_args__ = (Index('uq_system_department_name_ci',func.lower(name),unique=True),)
    aliases = mapped_column(JSON, nullable=False, default=list)
    revision = mapped_column(Integer, nullable=False, default=1)
    updated_by = mapped_column(Uuid, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class DepartmentMember(Base):
    __tablename__ = 'system_department_member'
    department_id = mapped_column(Uuid, ForeignKey('system_department.id', ondelete='CASCADE'), primary_key=True)
    user_id = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='CASCADE'), primary_key=True, index=True)
    position = mapped_column(String(50), nullable=False, default='')
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
