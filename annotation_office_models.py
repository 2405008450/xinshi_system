"""Office 会话与保存任务；仅通过显式迁移建表。"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Uuid, text

from models import Base


class AnnotationOfficeSession(Base):
    __tablename__ = 'annotation_office_session'
    __table_args__ = (
        Index('uq_annotation_office_writer', 'file_id', unique=True,
              postgresql_where=text("mode = 'edit' AND state IN ('open','saving')"),
              sqlite_where=text("mode = 'edit' AND state IN ('open','saving')")),
    )
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid, ForeignKey('annotation_project.id', ondelete='CASCADE'), nullable=False, index=True)
    file_id = Column(Uuid, ForeignKey('annotation_material_file.id', ondelete='CASCADE'))
    base_version_id = Column(Uuid)
    owner_id = Column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    owner_name = Column(String(255), nullable=False)
    mode = Column(String(10), nullable=False)
    state = Column(String(20), nullable=False, default='open')
    document_key = Column(String(64), nullable=False, unique=True)
    original_name = Column(String(255), nullable=False)
    folder_id = Column(Uuid)
    source_upload_id = Column(Uuid)
    staged_upload_id = Column(Uuid)
    staged_revision = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False)
    lease_until = Column(DateTime(timezone=True), nullable=False)
    active_save_id = Column(Uuid)
    saved_version_id = Column(Uuid)


class AnnotationOfficeSave(Base):
    __tablename__ = 'annotation_office_save'
    id = Column(Uuid, primary_key=True)
    session_id = Column(Uuid, ForeignKey('annotation_office_session.id', ondelete='CASCADE'), nullable=False, index=True)
    state = Column(String(20), nullable=False)
    revision = Column(Integer, nullable=False, default=0)
    error = Column(String(500))
    created_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    version_id = Column(Uuid)


OFFICE_TABLES = [AnnotationOfficeSession.__table__, AnnotationOfficeSave.__table__]
