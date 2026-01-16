from typing import Optional
import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKeyConstraint, PrimaryKeyConstraint, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class AppUser(Base):
    __tablename__ = 'app_user'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='app_user_pkey'),
        UniqueConstraint('username', name='app_user_username_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('true'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    project: Mapped[list['Project']] = relationship('Project', back_populates='app_user')
    user_role: Mapped[list['UserRole']] = relationship('UserRole', back_populates='user')
    project_file: Mapped[list['ProjectFile']] = relationship('ProjectFile', back_populates='app_user')


class Role(Base):
    __tablename__ = 'role'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='role_pkey'),
        UniqueConstraint('role_name', name='role_role_name_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    role_name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    user_role: Mapped[list['UserRole']] = relationship('UserRole', back_populates='role')


class Project(Base):
    __tablename__ = 'project'
    __table_args__ = (
        ForeignKeyConstraint(['created_by'], ['app_user.id'], ondelete='SET NULL', name='fk_project_creator'),
        PrimaryKeyConstraint('id', name='project_pkey'),
        UniqueConstraint('project_no', name='project_project_no_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    project_no: Mapped[str] = mapped_column(String(50), nullable=False)
    client_name: Mapped[Optional[str]] = mapped_column(String(255))
    project_type: Mapped[Optional[str]] = mapped_column(String(50))
    source_language: Mapped[Optional[str]] = mapped_column(String(50))
    target_language: Mapped[Optional[str]] = mapped_column(String(50))
    word_count: Mapped[Optional[str]] = mapped_column(String(50))
    deadline: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[Optional[str]] = mapped_column(String(50))
    sales_owner: Mapped[Optional[str]] = mapped_column(String(255))
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    app_user: Mapped[Optional['AppUser']] = relationship('AppUser', back_populates='project')
    project_file: Mapped[list['ProjectFile']] = relationship('ProjectFile', back_populates='project')


class UserRole(Base):
    __tablename__ = 'user_role'
    __table_args__ = (
        ForeignKeyConstraint(['role_id'], ['role.id'], ondelete='CASCADE', name='fk_role'),
        ForeignKeyConstraint(['user_id'], ['app_user.id'], ondelete='CASCADE', name='fk_user'),
        PrimaryKeyConstraint('id', name='user_role_pkey'),
        UniqueConstraint('user_id', 'role_id', name='uq_user_role')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    role: Mapped['Role'] = relationship('Role', back_populates='user_role')
    user: Mapped['AppUser'] = relationship('AppUser', back_populates='user_role')


class ProjectFile(Base):
    __tablename__ = 'project_file'
    __table_args__ = (
        ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE', name='fk_project'),
        ForeignKeyConstraint(['uploaded_by'], ['app_user.id'], ondelete='SET NULL', name='fk_uploader'),
        PrimaryKeyConstraint('id', name='project_file_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(50))
    file_ext: Mapped[Optional[str]] = mapped_column(String(20))
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    storage_type: Mapped[Optional[str]] = mapped_column(String(50))
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    project: Mapped['Project'] = relationship('Project', back_populates='project_file')
    app_user: Mapped[Optional['AppUser']] = relationship('AppUser', back_populates='project_file')
