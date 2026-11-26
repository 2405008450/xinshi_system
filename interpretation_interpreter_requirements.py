"""口译译员独立要求附表，保持既有项目表不变。"""
from sqlalchemy import Column,ForeignKey,JSON,Uuid,DateTime,inspect
from fastapi import HTTPException
from models import Base
from interpretation_models import InterpretationProject
from annotation_progress_time import business_now

class InterpretationInterpreterRequirements(Base):
    __tablename__='interpretation_interpreter_requirements'
    project_id=Column(Uuid,ForeignKey('interpretation_project.id',ondelete='CASCADE'),primary_key=True)
    values=Column(JSON,nullable=False)
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


def ready(db):
    if not hasattr(db,'connection'):return False
    key='_interpretation_interpreter_requirements_ready'
    if key not in db.info:db.info[key]=inspect(db.connection()).has_table(InterpretationInterpreterRequirements.__tablename__)
    return db.info[key]


def save(db,project,requirements):
    if requirements is None:return
    incoming=requirements.model_dump(exclude_unset=True)
    if not incoming:return
    if not ready(db):
        if any(incoming.values()):raise HTTPException(503,'译员独立要求表尚未初始化')
        return
    row=db.get(InterpretationInterpreterRequirements,project.id)
    values={**(row.values if row else {}),**incoming}
    if row:
        if row.values!=values:row.values=values;row.updated_at=business_now()
    elif any(values.values()):db.add(InterpretationInterpreterRequirements(project_id=project.id,values=values))


def attach(db,projects):
    values={}
    if projects and ready(db):
        values={row.project_id:row.values for row in db.query(InterpretationInterpreterRequirements).filter(
            InterpretationInterpreterRequirements.project_id.in_([project.id for project in projects]))}
    for project in projects:project.interpreter_requirements=dict(values.get(project.id,{}))


REQUIREMENT_LABELS={'bring_vehicle':'带车要求','driving':'开车要求','driving_license':'驾照要求','certificates':'证书要求',
    'photos':'照片要求','audio':'音频要求','video':'视频要求','interview':'面试要求','guide_licenses':'导游证等证件要求',
    'passport':'护照要求','visa':'签证要求','hong_kong_macau_permit':'港澳通行证及签注要求'}


def requirement_lines(values):
    """邮件与会话共用的附加要求文本；性别、水平和方向由原正文提供。"""
    lines=[]
    for key,label in [('interpreter_height_requirement','译员身高'),('interpreter_appearance_requirement','译员相貌'),('interpreter_dress_requirement','着装要求')]:
        if values.get(key):lines.append(f'{label}：{values[key]}')
    details=values.get('interpreter_requirements') or {}
    lines.extend(f'{label}：{details[key]}' for key,label in REQUIREMENT_LABELS.items() if details.get(key))
    return lines
