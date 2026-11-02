"""工作台口译项目今日安排，复用标注项目的输入协议和弹窗。"""
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, CheckConstraint, Uuid, inspect, or_, select

from models import Base, Client, SubClient
from interpretation_models import InterpretationProject
from annotation_work_status import ArrangementWrite, lock_user
from chat_time import now, api_time
from work_report_dates import report_business_date
from my_project_tasks import interpretation_task_filter


class InterpretationWorkDay(Base):
    __tablename__='interpretation_work_day'
    __table_args__=(
        UniqueConstraint('user_id','project_id','work_date',name='uq_interpretation_work_day'),
        CheckConstraint("arrangement_status IN ('in_progress','not_today')",name='ck_interpretation_work_day_status'),
        CheckConstraint("remaining_time IS NULL OR remaining_time IN ('under_30','30_60','1_2h','2_5h','5_10h','over_10h')",name='ck_interpretation_work_day_remaining'),
        CheckConstraint('revision >= 1',name='ck_interpretation_work_day_revision'),
    )
    id=Column(Uuid,primary_key=True,default=uuid4)
    user_id=Column(Uuid,ForeignKey('app_user.id',ondelete='CASCADE'),nullable=False)
    project_id=Column(Uuid,ForeignKey('interpretation_project.id',ondelete='CASCADE'),nullable=False)
    work_date=Column(Date,nullable=False)
    arrangement_status=Column(String(20),nullable=False)
    remaining_time=Column(String(20))
    entered_at=Column(DateTime(timezone=True))
    revision=Column(Integer,nullable=False)
    updated_at=Column(DateTime(timezone=True),nullable=False)


def ready(db):
    return inspect(db.connection()).has_table(InterpretationWorkDay.__tablename__)


def project_for(db,user,project_id,lock=False):
    if lock:
        db.query(InterpretationProject).filter_by(id=project_id).with_for_update().populate_existing().first()
    project=db.query(InterpretationProject).outerjoin(Client,InterpretationProject.client_id==Client.id).outerjoin(
        SubClient,InterpretationProject.sub_client_id==SubClient.id).filter(
        InterpretationProject.id==project_id,interpretation_task_filter(db,user)).first()
    if not project:
        raise HTTPException(404,'未找到本人工作台范围内未取消、未结款的口译项目')
    return project


def latest(db,user_id,project_id,day):
    return db.query(InterpretationWorkDay).filter(InterpretationWorkDay.user_id==user_id,
        InterpretationWorkDay.project_id==project_id,InterpretationWorkDay.work_date<=day).order_by(
        InterpretationWorkDay.work_date.desc()).first()


def state_data(row):
    return api_time(dict(revision=row.revision if row else 0,
        arrangement_status=row.arrangement_status if row else 'in_progress',
        remaining_time=row.remaining_time if row else None,
        entered_at=row.entered_at if row else None,cumulative_minutes=0,submissions=[]))


def today_filter(db,user):
    if not ready(db):
        return InterpretationProject.id.is_not(None)
    state=select(InterpretationWorkDay.arrangement_status).where(
        InterpretationWorkDay.user_id==user.id,InterpretationWorkDay.project_id==InterpretationProject.id,
        InterpretationWorkDay.work_date<=report_business_date(now())).order_by(
        InterpretationWorkDay.work_date.desc()).limit(1).correlate(InterpretationProject).scalar_subquery()
    return or_(state.is_(None),state=='in_progress')


def context(db,user,project_id):
    if not ready(db):
        return {'ready':False,'items':[]}
    project=project_for(db,user,project_id)
    day=report_business_date(now())
    row=latest(db,user.id,project.id,day)
    return api_time(dict(ready=True,work_date=day,items=[dict(id=str(project.id),orderNo=project.order_no,
        projectName=project.project_name,projectStatus=project.project_status,**state_data(row))]))


def save(db,user,project_id,payload:ArrangementWrite):
    if not ready(db):
        raise HTTPException(503,'口译今日安排表尚未初始化')
    lock_user(db,user)
    project=project_for(db,user,project_id,lock=True)
    stamp=now();day=report_business_date(stamp)
    previous=latest(db,user.id,project.id,day)
    revision=previous.revision if previous else 0
    if revision!=payload.revision:
        raise HTTPException(409,'今日安排已更新，请刷新后重试')
    row=previous if previous and previous.work_date==day else None
    if row is None:
        row=InterpretationWorkDay(user_id=user.id,project_id=project.id,work_date=day,
            arrangement_status=previous.arrangement_status if previous else 'in_progress',
            remaining_time=previous.remaining_time if previous else None,
            entered_at=stamp if not previous or previous.arrangement_status=='in_progress' else None,
            revision=revision+1,updated_at=stamp)
        db.add(row)
    else:
        row.revision+=1
    row.arrangement_status=payload.arrangement_status
    row.remaining_time=payload.remaining_time
    row.updated_at=stamp
    if payload.arrangement_status=='in_progress' and row.entered_at is None:
        row.entered_at=stamp
    db.commit()
    return state_data(row)
