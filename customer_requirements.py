"""Append-only customer requirements, organized by project type and field."""
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, Uuid, inspect, or_
from sqlalchemy.orm import Session

from annotation_models import AnnotationProject
from annotation_progress_time import business_datetime, business_now
from database import get_db
from interpretation_models import InterpretationProject
from models import Base, Client, SubClient, TranslationProject
from recruitment_models import RecruitmentProject
from routers.auth import get_current_user, require_any_permission, require_permission, user_has_permission


Module = Literal['translation', 'interpretation', 'annotation', 'recruitment']
FIELDS = {
    'translation': {'customerRequirementProfessional', 'customerRequirementSpecial', 'remarks'},
    'interpretation': {'taskDescription', 'interpreterSpecialRequirements', 'remarks'},
    'annotation': {'taskDescription', 'potentialDemand'},
    'recruitment': {'jobDescription', 'remarks'},
}
MODELS = {
    'translation': TranslationProject,
    'interpretation': InterpretationProject,
    'annotation': AnnotationProject,
    'recruitment': RecruitmentProject,
}


class CustomerRequirement(Base):
    __tablename__ = 'customer_requirement_history'
    __table_args__ = (Index('ix_customer_requirement_history_lookup', 'client_id', 'module', 'field', 'added_at'),)

    id = Column(Uuid, primary_key=True, default=uuid4)
    client_id = Column(Uuid, ForeignKey('client.id', ondelete='CASCADE'), nullable=False)
    module = Column(String(30), nullable=False)
    field = Column(String(60), nullable=False)
    content = Column(Text, nullable=False)
    added_at = Column(DateTime(timezone=True), nullable=False, default=business_now)
    source_project_id = Column(Uuid)
    source_order_no = Column(String(100))


class RequirementUpdate(BaseModel):
    values: dict[str, str] = Field(min_length=1, max_length=10)
    project_id: UUID | None = None


router = APIRouter(prefix='/clients/{client_id}/requirements', tags=['customer-requirements'])


def require_storage(db):
    if not inspect(db.connection()).has_table(CustomerRequirement.__tablename__):
        raise HTTPException(503, '客户要求历史表尚未初始化')


def entries_query(db, client_id, module):
    return db.query(CustomerRequirement).filter_by(client_id=client_id, module=module).order_by(
        CustomerRequirement.added_at.desc(), CustomerRequirement.id.desc(),
    )


def linked_project(db, client_id, module, project_id):
    model = MODELS[module]
    project = db.query(model.order_no).outerjoin(SubClient, SubClient.id == model.sub_client_id).filter(
        model.id == project_id,
        or_(model.client_id == client_id, SubClient.parent_client_id == client_id),
    ).first()
    if not project:
        raise HTTPException(422, '项目与客户的关联尚未保存或已变更，请先保存项目')
    return project


@router.get('/{module}', dependencies=[Depends(require_any_permission('clients:read', 'projects:write'))])
def read_requirements(client_id: UUID, module: Module, latest: bool = False,
                      db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not latest and not user_has_permission(db, user.id, 'clients:read'):
        raise HTTPException(403, '没有客户档案查看权限')
    if not db.get(Client, client_id):
        raise HTTPException(404, '客户不存在')
    require_storage(db)
    query = entries_query(db, client_id, module)
    if latest:
        return {'values': {
            field: row.content for field in FIELDS[module]
            if (row := query.filter_by(field=field).first()) is not None
        }}
    return {'items': [
        {'id': row.id, 'field': row.field, 'content': row.content,
         'added_at': business_datetime(row.added_at).isoformat(), 'source_order_no': row.source_order_no}
        for row in query
    ]}


@router.post('/{module}', dependencies=[Depends(require_permission('clients:write'))])
def append_requirements(client_id: UUID, module: Module, draft: RequirementUpdate,
                        db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not db.query(Client.id).filter_by(id=client_id).with_for_update().first():
        raise HTTPException(404, '客户不存在')
    values = {field: content.strip() for field, content in draft.values.items()}
    if values.keys() - FIELDS[module] or any(len(content) > 10000 for content in values.values()):
        raise HTTPException(422, '要求类别无效或单条内容超过 10000 字')
    project = None
    if draft.project_id:
        if not user_has_permission(db, user.id, 'projects:write'):
            raise HTTPException(403, '没有项目编辑权限')
        project = linked_project(db, client_id, module, draft.project_id)
    require_storage(db)
    added = 0
    now = business_now()
    for field, content in values.items():
        if not content:
            continue
        previous = entries_query(db, client_id, module).filter_by(field=field).first()
        if previous and previous.content == content:
            continue
        db.add(CustomerRequirement(
            client_id=client_id, module=module, field=field, content=content,
            added_at=now, source_project_id=draft.project_id,
            source_order_no=project.order_no if project else None,
        ))
        added += 1
    db.commit()
    return {'added': added}
