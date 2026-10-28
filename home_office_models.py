"""居家资格与逐日申请；审批未开发时只记录待审批。"""
from datetime import date,datetime
from uuid import UUID,uuid4
from sqlalchemy import Uuid,Date,DateTime,String,Text,ForeignKey,UniqueConstraint,Index,Integer,JSON
from sqlalchemy.orm import Mapped,mapped_column
from models import Base
from chat_time import now


class HomeOfficeQualification(Base):
    __tablename__='home_office_qualification'
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    client_id:Mapped[UUID]=mapped_column(Uuid,unique=True,nullable=False)
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    status:Mapped[str]=mapped_column(String(24),nullable=False,default='pending')
    approver_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)
    __table_args__=(Index('ix_home_office_qualification_user','user_id','created_at'),)


class HomeOfficeApplication(Base):
    __tablename__='home_office_application'
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    client_id:Mapped[UUID]=mapped_column(Uuid,unique=True,nullable=False)
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    requested_date:Mapped[date]=mapped_column(Date,nullable=False)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    status:Mapped[str]=mapped_column(String(24),nullable=False,default='pending')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)
    __table_args__=(UniqueConstraint('user_id','requested_date',name='uq_home_office_user_date'),Index('ix_home_office_application_user_date','user_id','requested_date'))


class HomeOfficeAnnualUsage(Base):
    __tablename__='home_office_annual_usage'
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),primary_key=True)
    year:Mapped[int]=mapped_column(Integer,primary_key=True)
    used_days:Mapped[int]=mapped_column(Integer,nullable=False)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    history:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    updated_by:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)
