from typing import Optional
import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Date, ForeignKeyConstraint, Index, Integer, Numeric, PrimaryKeyConstraint, SmallInteger, String, Text, Time, UniqueConstraint, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from project_roles import PROJECT_ROLE_DEFINITIONS

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
    department: Mapped[Optional[str]] = mapped_column(String(50))
    fixed_tasks: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    user_role: Mapped[list['UserRole']] = relationship('UserRole', back_populates='user')
    project_file: Mapped[list['ProjectFile']] = relationship('ProjectFile', back_populates='app_user')
    notifications: Mapped[list['AppNotification']] = relationship('AppNotification', back_populates='recipient', cascade='all, delete-orphan')
    chat_enabled_actions: Mapped[list['ChatProjectEnabled']] = relationship('ChatProjectEnabled', back_populates='operator')
    chat_sent_messages: Mapped[list['ChatProjectMessage']] = relationship('ChatProjectMessage', back_populates='sender')
    chat_mentions: Mapped[list['ChatProjectMention']] = relationship('ChatProjectMention', back_populates='mentioned_user')
    shift_templates: Mapped[list['EmployeeShiftTemplate']] = relationship(
        'EmployeeShiftTemplate',
        back_populates='user',
        cascade='all, delete-orphan',
        foreign_keys='EmployeeShiftTemplate.user_id',
    )
    shift_overrides: Mapped[list['EmployeeShiftOverride']] = relationship(
        'EmployeeShiftOverride',
        back_populates='user',
        cascade='all, delete-orphan',
        foreign_keys='EmployeeShiftOverride.user_id',
    )
    shift_locks: Mapped[list['EmployeeShiftLock']] = relationship(
        'EmployeeShiftLock',
        back_populates='user',
        cascade='all, delete-orphan',
        foreign_keys='EmployeeShiftLock.user_id',
    )
    leave_records: Mapped[list['EmployeeLeave']] = relationship(
        'EmployeeLeave',
        back_populates='employee',
        foreign_keys='EmployeeLeave.employee_id',
    )


Index(
    'uq_app_user_email_normalized',
    func.lower(func.btrim(AppUser.email)),
    unique=True,
    postgresql_where=AppUser.email.is_not(None) & (func.btrim(AppUser.email) != ''),
)


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
    role_permissions: Mapped[list['RolePermission']] = relationship(
        'RolePermission',
        back_populates='role',
        cascade='all, delete-orphan'
    )

    @property
    def permissions(self) -> list[str]:
        if self.role_name in ('admin', '超级管理员'):
            return ['*']
        return sorted(item.permission_code for item in self.role_permissions)


class Client(Base):
    __tablename__ = 'client'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='client_pkey'),
        UniqueConstraint('client_code', name='client_client_code_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    client_code: Mapped[str] = mapped_column(String(50), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_short_name: Mapped[str] = mapped_column(String(100), nullable=False)
    english_name: Mapped[Optional[str]] = mapped_column(String(255))
    english_short_name: Mapped[Optional[str]] = mapped_column(String(100))
    client_manager: Mapped[Optional[str]] = mapped_column(String(100))
    manager_contact: Mapped[Optional[str]] = mapped_column(String(100))
    field_level1: Mapped[Optional[str]] = mapped_column(String(100))
    field_level2: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(50))
    province: Mapped[Optional[str]] = mapped_column(String(50))
    city: Mapped[Optional[str]] = mapped_column(String(50))
    district: Mapped[Optional[str]] = mapped_column(String(50))
    client_status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'pending'"))
    cooperation_start_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    projects: Mapped[list['TranslationProject']] = relationship('TranslationProject', back_populates='client')
    consultations: Mapped[list['Consultation']] = relationship('Consultation', back_populates='client')
    contact_records: Mapped[list['ClientContact']] = relationship('ClientContact', back_populates='client')
    sub_clients: Mapped[list['SubClient']] = relationship('SubClient', back_populates='parent_client', cascade='all, delete-orphan')


class ClientContact(Base):
    __tablename__ = 'client_contact'
    __table_args__ = (
        ForeignKeyConstraint(['client_id'], ['client.id'], ondelete='SET NULL', name='fk_client_contact_client'),
        PrimaryKeyConstraint('id', name='client_contact_pkey'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    client_code: Mapped[Optional[str]] = mapped_column(String(50))
    client_name: Mapped[Optional[str]] = mapped_column(String(255))
    client_short_name: Mapped[Optional[str]] = mapped_column(String(100))
    client_manager: Mapped[Optional[str]] = mapped_column(String(100))
    manager_contact: Mapped[Optional[str]] = mapped_column(String(100))
    visit_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    visit_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    visit_type: Mapped[Optional[str]] = mapped_column(String(50))
    client_attitude: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)
    follow_up_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    follow_up_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    follow_up_status: Mapped[Optional[str]] = mapped_column(Text)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    client: Mapped[Optional['Client']] = relationship('Client', back_populates='contact_records')


class SubClient(Base):
    __tablename__ = 'sub_client'
    __table_args__ = (
        ForeignKeyConstraint(['parent_client_id'], ['client.id'], ondelete='CASCADE', name='fk_sub_client_parent'),
        PrimaryKeyConstraint('id', name='sub_client_pkey'),
        UniqueConstraint('sub_client_code', name='sub_client_code_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    parent_client_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sub_client_code: Mapped[str] = mapped_column(String(60), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_short_name: Mapped[str] = mapped_column(String(100), nullable=False)
    english_name: Mapped[Optional[str]] = mapped_column(String(255))
    english_short_name: Mapped[Optional[str]] = mapped_column(String(100))
    client_manager: Mapped[Optional[str]] = mapped_column(String(100))
    manager_contact: Mapped[Optional[str]] = mapped_column(String(100))
    field_level1: Mapped[Optional[str]] = mapped_column(String(100))
    field_level2: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(50))
    province: Mapped[Optional[str]] = mapped_column(String(50))
    city: Mapped[Optional[str]] = mapped_column(String(50))
    district: Mapped[Optional[str]] = mapped_column(String(50))
    client_status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'pending'"))
    cooperation_start_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    parent_client: Mapped['Client'] = relationship('Client', back_populates='sub_clients')



class Consultation(Base):
    __tablename__ = 'consultation'
    __table_args__ = (
        ForeignKeyConstraint(['client_id'], ['client.id'], ondelete='SET NULL', name='fk_consultation_client'),
        ForeignKeyConstraint(['sub_client_id'], ['sub_client.id'], ondelete='SET NULL', name='fk_consultation_sub_client'),
        ForeignKeyConstraint(['customer_service_id'], ['app_user.id'], ondelete='SET NULL', name='fk_consultation_customer_service'),
        ForeignKeyConstraint(['sales_person_id'], ['app_user.id'], ondelete='SET NULL', name='fk_consultation_sales_person'),
        ForeignKeyConstraint(['editor_id'], ['app_user.id'], ondelete='SET NULL', name='fk_consultation_editor'),
        ForeignKeyConstraint(['follow_up_person_id'], ['app_user.id'], ondelete='SET NULL', name='fk_consultation_follow_up_person'),
        PrimaryKeyConstraint('id', name='consultation_pkey'),
        UniqueConstraint('consultation_code', name='consultation_code_key'),
        UniqueConstraint('idempotency_key', name='uq_consultation_idempotency_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    consultation_code: Mapped[str] = mapped_column(String(50), nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128))
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    sub_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    contact_name: Mapped[Optional[str]] = mapped_column(String(255))
    customer_order_no: Mapped[Optional[str]] = mapped_column(String(150))
    project_name: Mapped[Optional[str]] = mapped_column(String(500))
    project_intake: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    project_intake_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    consultation_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    consultation_method: Mapped[Optional[str]] = mapped_column(String(50))
    client_source: Mapped[Optional[str]] = mapped_column(String(100))
    source_keyword: Mapped[Optional[str]] = mapped_column(String(255))
    consultation_description: Mapped[Optional[str]] = mapped_column(Text)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    customer_service_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    sales_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'pending'"))
    consultation_type: Mapped[Optional[str]] = mapped_column(String(50))
    handling_method: Mapped[Optional[str]] = mapped_column(String(100))
    editor_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    follow_up_count: Mapped[Optional[int]] = mapped_column(server_default=text('0'))
    follow_up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    follow_up_status: Mapped[Optional[str]] = mapped_column(String(20))
    follow_up_remarks: Mapped[Optional[str]] = mapped_column(Text)
    follow_up_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    # Relationships
    client: Mapped[Optional['Client']] = relationship('Client', back_populates='consultations')
    customer_service: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[customer_service_id])
    sales_person: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[sales_person_id])
    editor: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[editor_id])
    follow_up_person: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[follow_up_person_id])
    translation_project: Mapped[Optional['TranslationProject']] = relationship(
        'TranslationProject',
        back_populates='consultation',
        uselist=False,
    )


class Translator(Base):
    __tablename__ = 'translator'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='translator_pkey'),
        UniqueConstraint('translator_code', name='translator_translator_code_key'),
        UniqueConstraint('resource_person_id', name='uq_translator_resource_person'),
        ForeignKeyConstraint(
            ['resource_person_id'], ['resource_person.id'], ondelete='SET NULL',
            name='fk_translator_resource_person'
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    # 兼容桥接：旧项目继续引用 translator.id，新资源库通过该字段关联统一人员主档。
    resource_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    translator_code: Mapped[Optional[str]] = mapped_column(String(50))
    translator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cooperation_type: Mapped[Optional[str]] = mapped_column(String(50))
    contact_info: Mapped[Optional[str]] = mapped_column(String(255))
    translation_type: Mapped[Optional[str]] = mapped_column(String(255))
    interpretation_level: Mapped[Optional[str]] = mapped_column(String(20))
    quality_score: Mapped[Optional[str]] = mapped_column(String(10))
    direction: Mapped[Optional[str]] = mapped_column(String(20))
    default_priority: Mapped[Optional[int]] = mapped_column(server_default=text('0'))
    schedule_remarks: Mapped[Optional[str]] = mapped_column(Text)
    # 扩展字段
    languages: Mapped[Optional[str]] = mapped_column(String(255))
    gender: Mapped[Optional[str]] = mapped_column(String(10))
    height: Mapped[Optional[str]] = mapped_column(String(20))
    appearance: Mapped[Optional[str]] = mapped_column(String(100))
    nationality: Mapped[Optional[str]] = mapped_column(String(50))
    ethnicity: Mapped[Optional[str]] = mapped_column(String(50))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    phone2: Mapped[Optional[str]] = mapped_column(String(50))
    email1: Mapped[Optional[str]] = mapped_column(String(100))
    email2: Mapped[Optional[str]] = mapped_column(String(100))
    resume_path: Mapped[Optional[str]] = mapped_column(String(500))
    other_contact: Mapped[Optional[str]] = mapped_column(String(255))
    overdue_count: Mapped[Optional[int]] = mapped_column(server_default=text('0'))
    overall_rating: Mapped[Optional[str]] = mapped_column(Text)
    first_contact_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    # 可用性与产能字段（项目助理周一/五更新）
    status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'standby'"))
    available_time_slot: Mapped[Optional[str]] = mapped_column(String(100))
    daily_accept_count: Mapped[Optional[int]] = mapped_column(Integer)
    hourly_speed: Mapped[Optional[int]] = mapped_column(Integer)
    daily_word_capacity: Mapped[Optional[int]] = mapped_column(Integer)
    can_cloud_edit: Mapped[Optional[bool]] = mapped_column(Boolean)
    can_revision: Mapped[Optional[bool]] = mapped_column(Boolean)
    domain_skills: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    availability_updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    projects: Mapped[list['TranslationProject']] = relationship('TranslationProject', back_populates='translator')
    schedules: Mapped[list['TranslatorSchedule']] = relationship(
        'TranslatorSchedule',
        back_populates='translator',
        cascade='all, delete-orphan'
    )


class TranslatorSchedule(Base):
    __tablename__ = 'translator_schedule'
    __table_args__ = (
        ForeignKeyConstraint(['translator_id'], ['translator.id'], ondelete='CASCADE', name='fk_translator_schedule_translator'),
        PrimaryKeyConstraint('id', name='translator_schedule_pkey'),
        UniqueConstraint('translator_id', 'schedule_date', name='uq_translator_schedule_date')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    translator_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    schedule_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    availability_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'available'"))
    available_time_slot: Mapped[Optional[str]] = mapped_column(String(100))
    remaining_capacity: Mapped[Optional[int]] = mapped_column(Integer)
    source_type: Mapped[Optional[str]] = mapped_column(String(30), server_default=text("'manual'"))
    source_ref: Mapped[Optional[str]] = mapped_column(String(100))
    last_confirmed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    translator: Mapped['Translator'] = relationship('Translator', back_populates='schedules')


class EmployeeShiftTemplate(Base):
    """员工周班次模板；同一生效日期的七行构成一个版本。"""
    __tablename__ = 'employee_shift_template'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['app_user.id'], ondelete='CASCADE', name='fk_employee_shift_template_user'),
        PrimaryKeyConstraint('id', name='employee_shift_template_pkey'),
        UniqueConstraint('user_id', 'weekday', 'effective_from', name='uq_employee_shift_template_version'),
        CheckConstraint('weekday >= 1 AND weekday <= 7', name='ck_employee_shift_template_weekday'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    effective_from: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    shift_code: Mapped[str] = mapped_column(String(30), nullable=False)
    start_time: Mapped[Optional[datetime.time]] = mapped_column(Time)
    end_time: Mapped[Optional[datetime.time]] = mapped_column(Time)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    user: Mapped['AppUser'] = relationship('AppUser', back_populates='shift_templates', foreign_keys=[user_id])


class EmployeeShiftOverride(Base):
    """员工单日班次覆盖；存在时优先于周模板。"""
    __tablename__ = 'employee_shift_override'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['app_user.id'], ondelete='CASCADE', name='fk_employee_shift_override_user'),
        PrimaryKeyConstraint('id', name='employee_shift_override_pkey'),
        UniqueConstraint('user_id', 'schedule_date', name='uq_employee_shift_override_date'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    schedule_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    shift_code: Mapped[str] = mapped_column(String(30), nullable=False)
    start_time: Mapped[Optional[datetime.time]] = mapped_column(Time)
    end_time: Mapped[Optional[datetime.time]] = mapped_column(Time)
    note: Mapped[Optional[str]] = mapped_column(Text)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    user: Mapped['AppUser'] = relationship('AppUser', back_populates='shift_overrides', foreign_keys=[user_id])


class EmployeeShiftOverrideAudit(Base):
    """单日排班调整审计；恢复模板后仍保留调整原因和操作人。"""
    __tablename__ = 'employee_shift_override_audit'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['app_user.id'], ondelete='CASCADE', name='fk_shift_override_audit_user'),
        ForeignKeyConstraint(['changed_by'], ['app_user.id'], ondelete='SET NULL', name='fk_shift_override_audit_changed_by'),
        PrimaryKeyConstraint('id', name='employee_shift_override_audit_pkey'),
        Index('ix_shift_override_audit_user_date', 'user_id', 'schedule_date', 'changed_at'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    schedule_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    shift_code: Mapped[Optional[str]] = mapped_column(String(30))
    start_time: Mapped[Optional[datetime.time]] = mapped_column(Time)
    end_time: Mapped[Optional[datetime.time]] = mapped_column(Time)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    was_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    changed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class EmployeeShiftLock(Base):
    """员工固定班次锁定状态；按生效周保留锁定/解锁历史。"""
    __tablename__ = 'employee_shift_lock'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['app_user.id'], ondelete='CASCADE', name='fk_employee_shift_lock_user'),
        ForeignKeyConstraint(['changed_by'], ['app_user.id'], ondelete='SET NULL', name='fk_employee_shift_lock_changed_by'),
        PrimaryKeyConstraint('id', name='employee_shift_lock_pkey'),
        UniqueConstraint('user_id', 'effective_from', name='uq_employee_shift_lock_version'),
        Index('ix_employee_shift_lock_user_effective', 'user_id', 'effective_from'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    effective_from: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    reason: Mapped[Optional[str]] = mapped_column(String(500))
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    changed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))

    user: Mapped['AppUser'] = relationship('AppUser', back_populates='shift_locks', foreign_keys=[user_id])


class TranslationProject(Base):
    __tablename__ = 'translation_project'
    __table_args__ = (
        ForeignKeyConstraint(['client_id'], ['client.id'], ondelete='RESTRICT', name='fk_translation_project_client'),
        ForeignKeyConstraint(['sub_client_id'], ['sub_client.id'], ondelete='SET NULL', name='fk_translation_project_sub_client'),
        ForeignKeyConstraint(['consultation_id'], ['consultation.id'], ondelete='SET NULL', name='fk_translation_project_consultation'),
        ForeignKeyConstraint(['translator_id'], ['translator.id'], ondelete='SET NULL', name='fk_translation_project_translator'),
        ForeignKeyConstraint(['project_manager_id'], ['app_user.id'], ondelete='SET NULL', name='fk_translation_project_manager'),
        ForeignKeyConstraint(['pm_confirmed_by'], ['app_user.id'], ondelete='SET NULL', name='fk_translation_project_pm'),
        ForeignKeyConstraint(['created_by'], ['app_user.id'], ondelete='SET NULL', name='fk_translation_project_creator'),
        PrimaryKeyConstraint('id', name='translation_project_pkey'),
        UniqueConstraint('order_no', name='translation_project_order_no_key'),
        UniqueConstraint('consultation_id', name='uq_translation_project_consultation')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    order_no: Mapped[str] = mapped_column(String(50), nullable=False)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_type: Mapped[Optional[str]] = mapped_column(String(50))
    consultation_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    file_type_secondary: Mapped[Optional[str]] = mapped_column(String(100))
    project_contract_type: Mapped[Optional[str]] = mapped_column(String(100))
    project_contract_status: Mapped[Optional[str]] = mapped_column(String(100))
    quotation_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text('false'),
    )
    quotation_status: Mapped[Optional[str]] = mapped_column(String(100))
    quotation_path: Mapped[Optional[str]] = mapped_column(Text)
    customer_requirement_professional: Mapped[Optional[str]] = mapped_column(Text)
    customer_requirement_special: Mapped[Optional[str]] = mapped_column(Text)
    
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    sub_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    # 客户公司内部用于追踪外包项目的单号。
    customer_order_no: Mapped[Optional[str]] = mapped_column(String(100))
    email_subject_preview: Mapped[Optional[str]] = mapped_column(Text)
    service_content: Mapped[Optional[str]] = mapped_column(String(255))
    customer_reception_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    customer_deadline_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    sent_to_client_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    client_feedback: Mapped[Optional[str]] = mapped_column(Text)
    
    language_pair: Mapped[Optional[str]] = mapped_column(String(500))
    priority: Mapped[Optional[str]] = mapped_column(String(50))
    
    project_status: Mapped[Optional[str]] = mapped_column(String(50))
    # 管理层主负责人；与工作流当前处理人分离。
    project_manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    pm_confirmed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    major_project_manager_confirmation: Mapped[Optional[str]] = mapped_column(String(255))
    
    translator_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    translator_assignment_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    
    translator_delivery_progress: Mapped[Optional[str]] = mapped_column(String(20))
    pre_review_qc_progress: Mapped[Optional[str]] = mapped_column(String(20))
    review1_progress: Mapped[Optional[str]] = mapped_column(String(20))
    review2_progress: Mapped[Optional[str]] = mapped_column(String(20))
    post_review_qc_progress: Mapped[Optional[str]] = mapped_column(String(20))
    layout_progress: Mapped[Optional[str]] = mapped_column(String(20))
    consolidation_progress: Mapped[Optional[str]] = mapped_column(String(20))

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    # 历史上误建为笔译的标注项目迁移标记；保留原记录及其工作流/文件关系。
    annotation_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    annotation_migrated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    # 网络文件路径（如 \\win-server\xxx）
    network_file_path: Mapped[Optional[str]] = mapped_column(String(500))
    # 老系统稿件安排中的“参考文件路径一”，稿件安排通过 translation_project_id 读取。
    reference_file_path_one: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    client: Mapped[Optional['Client']] = relationship('Client', back_populates='projects')
    sub_client: Mapped[Optional['SubClient']] = relationship('SubClient', foreign_keys=[sub_client_id])
    consultation: Mapped[Optional['Consultation']] = relationship(
        'Consultation',
        back_populates='translation_project',
    )
    translator: Mapped[Optional['Translator']] = relationship('Translator', back_populates='projects')
    project_manager: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[project_manager_id])
    project_role_assignments: Mapped[list['ProjectRoleAssignment']] = relationship(
        'ProjectRoleAssignment',
        back_populates='project',
        cascade='all, delete-orphan',
    )
    pm_user: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[pm_confirmed_by])
    creator: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[created_by])
    
    project_file: Mapped[list['ProjectFile']] = relationship('ProjectFile', back_populates='translation_project', cascade='all, delete-orphan')
    workflow_instance: Mapped[Optional['WorkflowInstance']] = relationship('WorkflowInstance', back_populates='translation_project', uselist=False, cascade='all, delete-orphan')
    notifications: Mapped[list['AppNotification']] = relationship('AppNotification', back_populates='project')
    chat_setting: Mapped[Optional['ChatProjectEnabled']] = relationship('ChatProjectEnabled', back_populates='project', uselist=False, cascade='all, delete-orphan')
    chat_messages: Mapped[list['ChatProjectMessage']] = relationship('ChatProjectMessage', back_populates='project', cascade='all, delete-orphan')
    sub_orders: Mapped[list['TranslationSubOrder']] = relationship('TranslationSubOrder', back_populates='parent_project', cascade='all, delete-orphan')

    @property
    def translator_name(self) -> Optional[str]:
        """通过译员外键返回姓名，供项目详情接口直接展示。"""
        return self.translator.translator_name if self.translator else None

    @property
    def project_manager_name(self) -> Optional[str]:
        """返回项目管理层主负责人的显示名称。"""
        if not self.project_manager:
            return None
        return self.project_manager.full_name or self.project_manager.username

    @property
    def role_assignments(self) -> list[dict]:
        """统一返回项目经理与关系表中的项目固定角色。"""
        relation_by_code = {
            item.role_code: item for item in (self.project_role_assignments or [])
        }
        result = []
        for definition in PROJECT_ROLE_DEFINITIONS:
            role_code = definition['role_code']
            if role_code == 'project_manager':
                assignee = self.project_manager
                assignee_id = self.project_manager_id
            else:
                relation = relation_by_code.get(role_code)
                assignee = relation.assignee if relation else None
                assignee_id = relation.assignee_id if relation else None
            result.append({
                'role_code': role_code,
                'role_name': definition['role_name'],
                'assignee_id': assignee_id,
                'assignee_name': (
                    (assignee.full_name or assignee.username) if assignee else None
                ),
                'assignment_type': 'direct' if assignee_id else 'role_pool',
            })
        return result


class ProjectRoleAssignment(Base):
    """母项目的固定角色负责人；项目经理继续使用原字段。"""
    __tablename__ = 'project_role_assignment'
    __table_args__ = (
        ForeignKeyConstraint(
            ['translation_project_id'], ['translation_project.id'],
            ondelete='CASCADE', name='fk_project_role_assignment_project',
        ),
        ForeignKeyConstraint(
            ['assignee_id'], ['app_user.id'],
            ondelete='CASCADE', name='fk_project_role_assignment_assignee',
        ),
        PrimaryKeyConstraint('id', name='project_role_assignment_pkey'),
        UniqueConstraint(
            'translation_project_id', 'role_code',
            name='uq_project_role_assignment_project_role',
        ),
        CheckConstraint(
            "role_code IN ('project_specialist', 'project_assistant', 'layout_specialist')",
            name='ck_project_role_assignment_role_code',
        ),
        Index('ix_project_role_assignment_assignee', 'assignee_id'),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text('gen_random_uuid()')
    )
    translation_project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    role_code: Mapped[str] = mapped_column(String(50), nullable=False)
    assignee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, server_default=text('CURRENT_TIMESTAMP')
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, server_default=text('CURRENT_TIMESTAMP')
    )

    project: Mapped['TranslationProject'] = relationship(
        'TranslationProject', back_populates='project_role_assignments'
    )
    assignee: Mapped['AppUser'] = relationship('AppUser', foreign_keys=[assignee_id])


class TranslationSubOrder(Base):
    """翻译子订单表（母订单的下级子任务），字段与 TranslationProject 同步对齐"""
    __tablename__ = 'translation_sub_order'
    __table_args__ = (
        ForeignKeyConstraint(['parent_project_id'], ['translation_project.id'], ondelete='CASCADE', name='fk_sub_order_parent_project'),
        ForeignKeyConstraint(['translator_id'], ['translator.id'], ondelete='SET NULL', name='fk_sub_order_translator'),
        ForeignKeyConstraint(['created_by'], ['app_user.id'], ondelete='SET NULL', name='fk_sub_order_creator'),
        PrimaryKeyConstraint('id', name='translation_sub_order_pkey'),
        UniqueConstraint('sub_order_no', name='translation_sub_order_no_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    parent_project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sub_order_no: Mapped[str] = mapped_column(String(60), nullable=False)  # 如 TP-260302-014.001
    sub_project_name: Mapped[Optional[str]] = mapped_column(String(255))

    # 文件/语言/字数
    file_type_secondary: Mapped[Optional[str]] = mapped_column(String(100))
    language_pair: Mapped[Optional[str]] = mapped_column(String(500))
    priority: Mapped[Optional[str]] = mapped_column(String(50))

    # 时间节点（子订单独立的时间）
    customer_deadline_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    sent_to_client_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    client_feedback: Mapped[Optional[str]] = mapped_column(Text)

    # 译员信息
    translator_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    translator_assignment_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    # 各流程进度（与母订单字段一致）
    status: Mapped[Optional[str]] = mapped_column(String(50), server_default=text("'pending'"))
    translator_delivery_progress: Mapped[Optional[str]] = mapped_column(String(20))
    pre_review_qc_progress: Mapped[Optional[str]] = mapped_column(String(20))
    review_progress: Mapped[Optional[str]] = mapped_column(String(20))
    review1_progress: Mapped[Optional[str]] = mapped_column(String(20))
    review2_progress: Mapped[Optional[str]] = mapped_column(String(20))
    post_review_qc_progress: Mapped[Optional[str]] = mapped_column(String(20))
    layout_progress: Mapped[Optional[str]] = mapped_column(String(20))
    consolidation_progress: Mapped[Optional[str]] = mapped_column(String(20))

    # 网络文件路径（如 \\\\win-server\\xxx）
    network_file_path: Mapped[Optional[str]] = mapped_column(String(500))

    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    # Relationships
    parent_project: Mapped['TranslationProject'] = relationship('TranslationProject', back_populates='sub_orders')
    translator: Mapped[Optional['Translator']] = relationship('Translator', foreign_keys=[translator_id])
    creator: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[created_by])
    workflow_instance: Mapped[Optional['WorkflowInstance']] = relationship('WorkflowInstance', back_populates='sub_order', uselist=False, cascade='all, delete-orphan')

    @property
    def translator_name(self) -> Optional[str]:
        """通过译员外键返回姓名，供子订单详情接口直接展示。"""
        return self.translator.translator_name if self.translator else None


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


class RolePermission(Base):
    __tablename__ = 'role_permission'
    __table_args__ = (
        ForeignKeyConstraint(['role_id'], ['role.id'], ondelete='CASCADE', name='fk_role_permission_role'),
        PrimaryKeyConstraint('id', name='role_permission_pkey'),
        UniqueConstraint('role_id', 'permission_code', name='uq_role_permission')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    permission_code: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    role: Mapped['Role'] = relationship('Role', back_populates='role_permissions')


class ProjectFile(Base):
    __tablename__ = 'project_file'
    __table_args__ = (
        ForeignKeyConstraint(['translation_project_id'], ['translation_project.id'], ondelete='CASCADE', name='fk_project_file_project'),
        ForeignKeyConstraint(['uploaded_by'], ['app_user.id'], ondelete='SET NULL', name='fk_uploader'),
        PrimaryKeyConstraint('id', name='project_file_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    translation_project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)          # 原文路径
    dispatch_path: Mapped[Optional[str]] = mapped_column(Text)               # 派稿文路径
    translation_path: Mapped[Optional[str]] = mapped_column(Text)            # 译文路径
    translator_return_path: Mapped[Optional[str]] = mapped_column(Text)       # 译员发回路径
    client_delivery_path: Mapped[Optional[str]] = mapped_column(Text)        # 发客户路径
    project_feedback_path: Mapped[Optional[str]] = mapped_column(Text)        # 项目反馈路径
    feedback_delivery_path: Mapped[Optional[str]] = mapped_column(Text)       # 反馈后发客户路径
    translation_domain_level1: Mapped[Optional[str]] = mapped_column(String(255))  # 翻译文本领域一级
    translation_domain_level2: Mapped[Optional[str]] = mapped_column(String(255))  # 翻译文本领域二级
    file_type: Mapped[Optional[str]] = mapped_column(String(255))             # 文件类型一级（兼容原字段）
    file_type_secondary: Mapped[Optional[str]] = mapped_column(String(255))   # 文件类型二级
    file_format: Mapped[Optional[str]] = mapped_column(String(100))           # 文件格式
    file_attribute_level1: Mapped[Optional[str]] = mapped_column(String(255)) # 文件属性一级
    file_attribute_level2: Mapped[Optional[str]] = mapped_column(String(255)) # 文件属性二级
    file_attribute_level3: Mapped[Optional[str]] = mapped_column(String(255)) # 文件属性三级
    file_difficulty: Mapped[Optional[str]] = mapped_column(String(100))       # 文件难度
    file_ext: Mapped[Optional[str]] = mapped_column(String(20))
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    storage_type: Mapped[Optional[str]] = mapped_column(String(50))
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    translation_project: Mapped['TranslationProject'] = relationship('TranslationProject', back_populates='project_file')
    app_user: Mapped[Optional['AppUser']] = relationship('AppUser', back_populates='project_file')

    @property
    def order_no(self):
        return self.translation_project.order_no if self.translation_project else None

    @property
    def project_name(self):
        return self.translation_project.project_name if self.translation_project else None

    @property
    def project_status(self):
        return self.translation_project.project_status if self.translation_project else None



class ChatProjectEnabled(Base):
    __tablename__ = 'chat_project_enabled'
    __table_args__ = (
        ForeignKeyConstraint(['project_id'], ['translation_project.id'], ondelete='CASCADE', name='fk_chat_project_enabled_project'),
        ForeignKeyConstraint(['enabled_by'], ['app_user.id'], ondelete='SET NULL', name='fk_chat_project_enabled_operator'),
        PrimaryKeyConstraint('id', name='chat_project_enabled_pkey'),
        UniqueConstraint('project_id', name='uq_chat_project_enabled_project'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    enabled_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    enabled_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    project: Mapped['TranslationProject'] = relationship('TranslationProject', back_populates='chat_setting')
    operator: Mapped[Optional['AppUser']] = relationship('AppUser', back_populates='chat_enabled_actions')


class ChatProjectMessage(Base):
    __tablename__ = 'chat_project_message'
    __table_args__ = (
        ForeignKeyConstraint(['project_id'], ['translation_project.id'], ondelete='CASCADE', name='fk_chat_project_message_project'),
        ForeignKeyConstraint(['sender_user_id'], ['app_user.id'], ondelete='SET NULL', name='fk_chat_project_message_sender'),
        PrimaryKeyConstraint('id', name='chat_project_message_pkey'),
        Index('ix_chat_project_message_project_created_at', 'project_id', 'created_at'),
        Index('ix_chat_project_message_sender_user_id', 'sender_user_id'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sender_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    sender_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'user'"))
    content_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    event_data: Mapped[Optional[dict]] = mapped_column('metadata', JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    project: Mapped['TranslationProject'] = relationship('TranslationProject', back_populates='chat_messages')
    sender: Mapped[Optional['AppUser']] = relationship('AppUser', back_populates='chat_sent_messages')
    mentions: Mapped[list['ChatProjectMention']] = relationship('ChatProjectMention', back_populates='message', cascade='all, delete-orphan')
    attachment_links: Mapped[list['ChatProjectMessageAttachment']] = relationship(
        'ChatProjectMessageAttachment',
        back_populates='message',
        cascade='all, delete-orphan',
    )


class ChatProjectMention(Base):
    __tablename__ = 'chat_project_mention'
    __table_args__ = (
        ForeignKeyConstraint(['message_id'], ['chat_project_message.id'], ondelete='CASCADE', name='fk_chat_project_mention_message'),
        ForeignKeyConstraint(['mentioned_user_id'], ['app_user.id'], ondelete='CASCADE', name='fk_chat_project_mention_user'),
        PrimaryKeyConstraint('id', name='chat_project_mention_pkey'),
        UniqueConstraint('message_id', 'mentioned_user_id', name='uq_chat_project_mention_message_user'),
        Index('ix_chat_project_mention_user_id', 'mentioned_user_id'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    message_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    mentioned_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    mentioned_user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    message: Mapped['ChatProjectMessage'] = relationship('ChatProjectMessage', back_populates='mentions')
    mentioned_user: Mapped['AppUser'] = relationship('AppUser', back_populates='chat_mentions')


class ChatProjectAttachment(Base):
    __tablename__ = 'chat_project_attachment'
    __table_args__ = (
        ForeignKeyConstraint(['uploaded_by'], ['app_user.id'], ondelete='SET NULL', name='fk_chat_attachment_uploader'),
        PrimaryKeyConstraint('id', name='chat_project_attachment_pkey'),
        Index('ix_chat_project_attachment_created_at', 'created_at'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    message_links: Mapped[list['ChatProjectMessageAttachment']] = relationship(
        'ChatProjectMessageAttachment',
        back_populates='attachment',
        cascade='all, delete-orphan',
    )


class ChatProjectMessageAttachment(Base):
    __tablename__ = 'chat_project_message_attachment'
    __table_args__ = (
        ForeignKeyConstraint(['message_id'], ['chat_project_message.id'], ondelete='CASCADE', name='fk_chat_message_attachment_message'),
        ForeignKeyConstraint(['attachment_id'], ['chat_project_attachment.id'], ondelete='CASCADE', name='fk_chat_message_attachment_attachment'),
        PrimaryKeyConstraint('id', name='chat_project_message_attachment_pkey'),
        UniqueConstraint('message_id', 'attachment_id', name='uq_chat_message_attachment'),
        Index('ix_chat_message_attachment_attachment_id', 'attachment_id'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    message_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    attachment_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    message: Mapped['ChatProjectMessage'] = relationship('ChatProjectMessage', back_populates='attachment_links')
    attachment: Mapped['ChatProjectAttachment'] = relationship('ChatProjectAttachment', back_populates='message_links')


class AppNotification(Base):
    __tablename__ = 'app_notification'
    __table_args__ = (
        ForeignKeyConstraint(['recipient_user_id'], ['app_user.id'], ondelete='CASCADE', name='fk_app_notification_recipient'),
        ForeignKeyConstraint(['related_project_id'], ['translation_project.id'], ondelete='SET NULL', name='fk_app_notification_project'),
        PrimaryKeyConstraint('id', name='app_notification_pkey'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'workflow'"))
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    read_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    related_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    related_project_type: Mapped[Optional[str]] = mapped_column(String(30))
    related_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    recipient: Mapped['AppUser'] = relationship('AppUser', back_populates='notifications')
    project: Mapped[Optional['TranslationProject']] = relationship('TranslationProject', back_populates='notifications')


class WorkSchedule(Base):
    """每日工作安排表（排班管理），按日期存储，项目经理每日微调"""
    __tablename__ = 'work_schedule'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='work_schedule_pkey'),
        UniqueConstraint('schedule_date', name='work_schedule_date_key'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    schedule_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, unique=True)

    # 各板块数据以 JSONB 存储，前端直接读写整块 JSON
    shift_table: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    leave_notes: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    urgent_table_zh_en: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    urgent_table_en_zh: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    dept_person_data: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    not_scheduled_tasks: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    pm_rotation_order: Mapped[Optional[str]] = mapped_column(String(500))

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))


class EmployeeLeave(Base):
    """员工请假记录"""
    __tablename__ = 'employee_leave'
    __table_args__ = (
        ForeignKeyConstraint(['employee_id'], ['app_user.id'], ondelete='RESTRICT', name='fk_employee_leave_employee'),
        ForeignKeyConstraint(['created_by'], ['app_user.id'], ondelete='SET NULL', name='fk_employee_leave_created_by'),
        ForeignKeyConstraint(['updated_by'], ['app_user.id'], ondelete='SET NULL', name='fk_employee_leave_updated_by'),
        PrimaryKeyConstraint('id', name='employee_leave_pkey'),
        Index('ix_employee_leave_employee_time', 'employee_id', 'start_date', 'end_date'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    employee_name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    leave_type: Mapped[Optional[str]] = mapped_column(String(50))
    reason: Mapped[Optional[str]] = mapped_column(String(500))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    employee: Mapped['AppUser'] = relationship('AppUser', back_populates='leave_records', foreign_keys=[employee_id])


class FinanceRecord(Base):
    """财务主表：一单一条"""
    __tablename__ = 'finance_record'
    __table_args__ = (
        ForeignKeyConstraint(['project_id'], ['translation_project.id'], ondelete='RESTRICT', name='fk_finance_record_project'),
        ForeignKeyConstraint(['sales_person_id'], ['app_user.id'], ondelete='SET NULL', name='fk_finance_record_sales_person'),
        ForeignKeyConstraint(['follow_up_person_id'], ['app_user.id'], ondelete='SET NULL', name='fk_finance_record_follow_up_person'),
        ForeignKeyConstraint(['edited_by'], ['app_user.id'], ondelete='SET NULL', name='fk_finance_record_edited_by'),
        PrimaryKeyConstraint('id', name='finance_record_pkey'),
        UniqueConstraint('project_id', name='uq_finance_record_project'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sales_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    follow_up_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    settlement_method: Mapped[Optional[str]] = mapped_column(String(50))
    unit_price_excl_tax: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    unit_price_incl_tax: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    total_excl_tax: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    total_incl_tax: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    invoice_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'unissued'"))
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    edited_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    # Relationships
    project: Mapped['TranslationProject'] = relationship('TranslationProject', foreign_keys=[project_id])
    sales_person: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[sales_person_id])
    follow_up_person: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[follow_up_person_id])
    editor: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[edited_by])
    payments: Mapped[list['FinancePayment']] = relationship('FinancePayment', back_populates='finance_record', cascade='all, delete-orphan')


class FinancePayment(Base):
    """财务款项明细表：一单多条（定金/中期/尾款）"""
    __tablename__ = 'finance_payment'
    __table_args__ = (
        ForeignKeyConstraint(['finance_id'], ['finance_record.id'], ondelete='CASCADE', name='fk_finance_payment_finance'),
        ForeignKeyConstraint(['confirmed_by'], ['app_user.id'], ondelete='SET NULL', name='fk_finance_payment_confirmed_by'),
        PrimaryKeyConstraint('id', name='finance_payment_pkey'),
        UniqueConstraint('finance_id', 'stage_type', 'stage_no', name='uq_finance_payment_stage'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    finance_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    stage_type: Mapped[str] = mapped_column(String(20), nullable=False)  # deposit, mid, final
    stage_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    planned_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    actual_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    payment_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
    confirmed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    confirmed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('now()'))

    # Relationships
    finance_record: Mapped['FinanceRecord'] = relationship('FinanceRecord', back_populates='payments')
    confirmer: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[confirmed_by])
