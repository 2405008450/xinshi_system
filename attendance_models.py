"""考勤实际时刻与请假班次快照；不复用演示表。"""
from datetime import date,datetime
from uuid import UUID,uuid4
from sqlalchemy import Date,DateTime,JSON,String,Text,Integer,Uuid,UniqueConstraint,Index,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from models import Base
from chat_time import now

class AttendanceDay(Base):
    __tablename__='attendance_day'
    __table_args__=(UniqueConstraint('user_id','day',name='uq_attendance_user_day'),Index('ix_attendance_day_date','day'))
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    day:Mapped[date]=mapped_column(Date,nullable=False)
    check_in:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    check_out:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    shift_snapshot:Mapped[dict]=mapped_column(JSON,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class AttendanceLeave(Base):
    __tablename__='attendance_leave'
    __table_args__=(Index('ix_attendance_leave_user_time','user_id','start_at','end_at'),)
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    client_id:Mapped[UUID]=mapped_column(Uuid,unique=True,nullable=False)
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    start_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    end_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    days:Mapped[list]=mapped_column(JSON,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class AttendanceClockSession(Base):
    __tablename__='attendance_clock_session'
    __table_args__=(UniqueConstraint('user_id','day','segment',name='uq_attendance_clock_segment'),Index('ix_attendance_clock_user_day','user_id','day'))
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    day:Mapped[date]=mapped_column(Date,nullable=False)
    segment:Mapped[int]=mapped_column(Integer,nullable=False)
    check_in:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    check_out:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    shift_snapshot:Mapped[dict]=mapped_column(JSON,nullable=False)
    confirmations:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class AttendanceDelayStart(Base):
    __tablename__='attendance_delay_start'
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    client_id:Mapped[UUID]=mapped_column(Uuid,unique=True,nullable=False)
    user_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    requested_start:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)
    __table_args__=(Index('ix_attendance_delay_start_user_time','user_id','requested_start'),)
