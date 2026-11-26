"""四类项目共用客户来源附表，与项目保存处于同一事务。"""
from uuid import uuid4
from sqlalchemy import Column, String, Uuid, DateTime, CheckConstraint, event, inspect
from sqlalchemy.orm import Session, object_session, attributes
from fastapi import HTTPException

def storage_available(db):
    key = 'project_customer_source_storage'
    if key not in db.info:
        db.info[key] = inspect(db.connection()).has_table(ProjectCustomerSource.__tablename__)
    return db.info[key]


def customer_source_property(module):
    def read(project):
        if '_pending_customer_source' in project.__dict__:
            return project.__dict__['_pending_customer_source']
        db = object_session(project)
        if not db:
            return ''
        with db.no_autoflush:
            if project.id and storage_available(db):
                cache = db.info.setdefault('project_customer_source_reads', {})
                key = (module, project.id)
                if key not in cache:
                    ids = {item.id for item in db.identity_map.values() if isinstance(item, type(project)) and item.id}
                    ids.add(project.id)
                    cache.update({(module, item): None for item in ids})
                    rows = db.query(ProjectCustomerSource).filter(
                        ProjectCustomerSource.module == module, ProjectCustomerSource.project_id.in_(ids)).all()
                    cache.update({(module, row.project_id): row.content for row in rows})
                if cache[key] is not None:
                    return cache[key]
            consultation_id = getattr(project, 'consultation_id', None)
            if consultation_id:
                from models import Consultation
                return db.query(Consultation.client_source).filter_by(id=consultation_id).scalar() or ''
        return ''
    def write(project, value):
        if value is None:
            return
        value = str(value).strip()
        if len(value) > 500:
            raise ValueError('客户来源不能超过500字')
        project.__dict__['_pending_customer_source'] = value
        project.__dict__['_customer_source_module'] = module
        if inspect(project).persistent:
            attributes.flag_dirty(project)
    return property(read, write)


from models import Base
from annotation_progress_time import business_now

class ProjectCustomerSource(Base):
    __tablename__ = 'project_customer_source'
    __table_args__ = (CheckConstraint("module IN ('translation','interpretation','annotation','recruitment')", name='ck_project_customer_source_module'),)
    module = Column(String(30), primary_key=True)
    project_id = Column(Uuid, primary_key=True)
    content = Column(String(500), nullable=False, default='')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=business_now)



@event.listens_for(Session, 'before_flush')
def save_sources(db, _context, _instances):
    for project in list(db.new) + list(db.dirty):
        if '_pending_customer_source' not in project.__dict__ or project in db.deleted:
            continue
        content = project.__dict__['_pending_customer_source']
        if not storage_available(db):
            if content:
                raise HTTPException(503, '项目客户来源表尚未初始化')
            continue
        if not project.id:
            project.id = uuid4()
        key = (project.__dict__['_customer_source_module'], project.id)
        record = db.get(ProjectCustomerSource, key)
        if record is None:
            db.add(ProjectCustomerSource(module=key[0], project_id=key[1], content=content))
        elif record.content != content:
            record.content = content
            record.updated_at = business_now()


@event.listens_for(Session, 'after_flush_postexec')
@event.listens_for(Session, 'after_rollback')
def clear_source_cache(db, *_args):
    db.info.pop('project_customer_source_reads', None)
    for project in db.identity_map.values():
        project.__dict__.pop('_pending_customer_source', None)
        project.__dict__.pop('_customer_source_module', None)
