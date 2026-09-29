"""标注项目资料：暂存对象、逻辑文件、不可变版本和删除重试队列。"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from models import Base


class AnnotationMaterialUpload(Base):
    __tablename__ = 'annotation_material_upload'
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    uploaded_by = Column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    uploader_name = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    storage_key = Column(String(64), nullable=False, unique=True)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    consumed_at = Column(DateTime)


class AnnotationMaterialFile(Base):
    __tablename__ = 'annotation_material_file'
    __table_args__ = (CheckConstraint("category IN ('project','quotation','contract')", name='ck_annotation_material_category'),)
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid, ForeignKey('annotation_project.id', ondelete='CASCADE'), nullable=False, index=True)
    category = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AnnotationMaterialVersion(Base):
    __tablename__ = 'annotation_material_version'
    __table_args__ = (UniqueConstraint('file_id', 'version_no'),)
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    file_id = Column(Uuid, ForeignKey('annotation_material_file.id', ondelete='CASCADE'), nullable=False, index=True)
    upload_id = Column(Uuid, ForeignKey('annotation_material_upload.id'), nullable=False, unique=True)
    version_no = Column(Integer, nullable=False)


class AnnotationMaterialDeletion(Base):
    __tablename__ = 'annotation_material_deletion'
    storage_key = Column(String(64), primary_key=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(String(500))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


MATERIAL_TABLES = [model.__table__ for model in (
    AnnotationMaterialUpload, AnnotationMaterialFile, AnnotationMaterialVersion, AnnotationMaterialDeletion,
)]
