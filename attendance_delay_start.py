"""延迟上班申请及全体通知；不将申请自动视为已批准调班。"""
from datetime import datetime
from uuid import UUID,uuid4
from fastapi import HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import inspect
from attendance_models import AttendanceDelayStart as DelayStart
from chat_time import now,api_time


class DelayWrite(BaseModel):
    client_id:UUID
    requested_start:datetime
    reason:str=Field(min_length=1,max_length=1000)
    @field_validator('reason')
    @classmethod
    def clean(cls,value):
        if not value.strip():raise ValueError('请填写延迟上班事由')
        return value.strip()
    @field_validator('requested_start')
    @classmethod
    def local(cls,value):
        if value.tzinfo is None:raise ValueError('预计上班时间须携带+08:00时区')
        return api_time(value)


def ready(db):return inspect(db.connection()).has_table(DelayStart.__tablename__)
def active(user):
    if not user or not user.is_active or user.is_deleted:raise HTTPException(403,'账号不可用')
def serialize(row):return api_time({'id':row.id,'requested_start':row.requested_start,'reason':row.reason,'created_at':row.created_at,'status':'已申请并通知全体'})
def mine(db,user):
    active(user)
    return {'ready':ready(db),'items':[serialize(row) for row in db.query(DelayStart).filter_by(user_id=user.id).order_by(DelayStart.created_at.desc()).limit(100).all()] if ready(db) else []}


def submit(db,user,payload):
    from attendance_notifications import queue_attendance_notifications,publish_leave_notifications
    from attendance_clock import lock
    active(user)
    if not ready(db):raise HTTPException(503,'延迟上班申请表尚未初始化')
    lock(db,user)
    existing=db.query(DelayStart).filter_by(client_id=payload.client_id).first()
    if existing:
        if existing.user_id!=user.id:raise HTTPException(409,'申请标识已使用')
        return {'message':'申请已通知，请勿重复提交','record':serialize(existing)}
    if payload.requested_start.date()<now().date():raise HTTPException(422,'不能申请过去日期的延迟上班')
    row=DelayStart(id=uuid4(),client_id=payload.client_id,user_id=user.id,requested_start=payload.requested_start,reason=payload.reason,created_at=now());db.add(row)
    title=f'延迟上班申请 · {user.full_name or user.username}'
    content=f'{user.full_name or user.username} 申请延迟上班，预计上班时间：{payload.requested_start.strftime("%Y年%m月%d日 %H:%M")}（UTC+8）。事由：{payload.reason}'
    try:events=queue_attendance_notifications(db,user,row.id,title,content,'attendance_delay_start');db.commit()
    except Exception:db.rollback();raise
    publish_leave_notifications(events)
    return {'message':'延迟上班申请已保存并通知全体人员','record':serialize(row)}
