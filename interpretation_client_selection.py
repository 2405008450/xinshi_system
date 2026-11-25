"""口译项目客户选定译员标记，不改写既有安排表结构。"""
from sqlalchemy import Column, ForeignKey, Uuid, DateTime, inspect
from fastapi import HTTPException
from models import Base
from interpretation_models import InterpretationProject
from annotation_progress_time import business_now

class InterpretationClientSelectedInterpreter(Base):
    __tablename__ = 'interpretation_client_selected_interpreter'
    project_id = Column(Uuid, ForeignKey('interpretation_project.id', ondelete='CASCADE'), primary_key=True)
    translator_id = Column(Uuid, ForeignKey('translator.id', ondelete='CASCADE'), primary_key=True)
    selected_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


def ready(db):
    if not hasattr(db,'connection'):return False
    key='_interpretation_client_selection_ready'
    if key not in db.info:db.info[key]=inspect(db.connection()).has_table(InterpretationClientSelectedInterpreter.__tablename__)
    return db.info[key]


def save(db,project,items,translator_ids):
    if not ready(db):
        if any(getattr(item,'client_selected',None) for item in items):raise HTTPException(503,'客户选定译员标记表尚未初始化')
        return
    old={row.translator_id:row for row in db.query(InterpretationClientSelectedInterpreter).filter_by(project_id=project.id)}
    chosen={translator_ids[item.translator_id] for item in items
            if item.client_selected is True or (item.client_selected is None and translator_ids[item.translator_id] in old)}
    for key,row in old.items():
        if key not in chosen:db.delete(row)
    for key in chosen-old.keys():db.add(InterpretationClientSelectedInterpreter(project_id=project.id,translator_id=key))


def attach(db,projects):
    chosen=set()
    if projects and ready(db):
        chosen={(row.project_id,row.translator_id) for row in db.query(InterpretationClientSelectedInterpreter).filter(
            InterpretationClientSelectedInterpreter.project_id.in_([project.id for project in projects]))}
    for project in projects:
        for item in project.interpreter_assignments:item.client_selected=(project.id,item.translator_id) in chosen
