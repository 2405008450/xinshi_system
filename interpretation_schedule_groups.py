"""口译时间段与地点、方向的对应关系；不改写既有时间段表结构。"""
from fastapi import HTTPException
from sqlalchemy import Column, ForeignKey, JSON, Uuid, inspect
from models import Base


class InterpretationScheduleGroups(Base):
    __tablename__ = 'interpretation_project_schedule_groups'
    project_id = Column(Uuid, ForeignKey('interpretation_project.id', ondelete='CASCADE'), primary_key=True)
    groups = Column(JSON, nullable=False)


def ready(db):
    if not hasattr(db, 'connection'):return False
    if '_interpretation_schedule_groups_ready' not in db.info:
        db.info['_interpretation_schedule_groups_ready'] = inspect(db.connection()).has_table(InterpretationScheduleGroups.__tablename__)
    return db.info['_interpretation_schedule_groups_ready']


def save(db, project, ranges):
    grouped = any(item.locations is not None or item.language_directions is not None for item in ranges)
    if not ready(db):
        if grouped:raise HTTPException(503, '口译时间段分组表尚未初始化')
        return
    existing = db.get(InterpretationScheduleGroups, project.id)
    if not grouped:
        if existing:raise HTTPException(409, '该项目已按时间段分组，请重新打开项目窗口后保存')
        return
    groups = [dict(locations=item.locations, language_directions=[direction.model_dump(mode='json') for direction in item.language_directions]) for item in ranges]
    if existing:existing.groups = groups
    else:db.add(InterpretationScheduleGroups(project_id=project.id, groups=groups))


def attach(db, projects):
    if not projects or not ready(db):return
    plans = {row.project_id:row.groups for row in db.query(InterpretationScheduleGroups).filter(InterpretationScheduleGroups.project_id.in_([project.id for project in projects])).all()}
    for project in projects:
        groups = plans.get(project.id, [])
        for index, item in enumerate(project.time_ranges):
            group = groups[index] if index < len(groups) else {}
            item.locations = group.get('locations')
            item.language_directions = group.get('language_directions')
