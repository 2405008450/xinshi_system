"""标注项目资料：暂存对象、逻辑文件、不可变版本和删除重试队列。"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, text
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


class AnnotationMaterialFolder(Base):
    __tablename__ = 'annotation_material_folder'
    __table_args__ = (
        UniqueConstraint('project_id', 'parent_id', 'name', name='uq_annotation_material_folder_sibling'),
        Index('uq_annotation_material_folder_root', 'project_id', 'name', unique=True,
              postgresql_where=text('parent_id IS NULL'), sqlite_where=text('parent_id IS NULL')),
    )
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid, ForeignKey('annotation_project.id', ondelete='CASCADE'), nullable=False, index=True)
    parent_id = Column(Uuid, ForeignKey('annotation_material_folder.id', ondelete='CASCADE'))
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AnnotationMaterialFile(Base):
    __tablename__ = 'annotation_material_file'
    __table_args__ = (
        CheckConstraint("category IN ('project','quotation','contract')", name='ck_annotation_material_category'),
        CheckConstraint("folder_id IS NULL OR category = 'project'", name='ck_annotation_material_folder_category'),
    )
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid, ForeignKey('annotation_project.id', ondelete='CASCADE'), nullable=False, index=True)
    category = Column(String(20), nullable=False)
    folder_id = Column(Uuid, ForeignKey('annotation_material_folder.id', ondelete='SET NULL', name='fk_annotation_material_file_folder'), index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AnnotationMaterialVersion(Base):
    __tablename__ = 'annotation_material_version'
    __table_args__ = (UniqueConstraint('file_id', 'version_no'),)
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    file_id = Column(Uuid, ForeignKey('annotation_material_file.id', ondelete='CASCADE'), nullable=False, index=True)
    upload_id = Column(Uuid, ForeignKey('annotation_material_upload.id'), nullable=False, index=True)
    version_no = Column(Integer, nullable=False)


class AnnotationMaterialDeletion(Base):
    __tablename__ = 'annotation_material_deletion'
    storage_key = Column(String(64), primary_key=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(String(500))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


MATERIAL_TABLES = [model.__table__ for model in (
    AnnotationMaterialUpload, AnnotationMaterialFolder, AnnotationMaterialFile, AnnotationMaterialVersion, AnnotationMaterialDeletion,
)]
