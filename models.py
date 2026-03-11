from typing import Optional
import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Date, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
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
    department: Mapped[Optional[str]] = mapped_column(String(50))
    fixed_tasks: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

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
    sub_clients: Mapped[list['SubClient']] = relationship('SubClient', back_populates='parent_client', cascade='all, delete-orphan')


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
        ForeignKeyConstraint(['customer_service_id'], ['app_user.id'], ondelete='SET NULL', name='fk_consultation_customer_service'),
        ForeignKeyConstraint(['sales_person_id'], ['app_user.id'], ondelete='SET NULL', name='fk_consultation_sales_person'),
        ForeignKeyConstraint(['editor_id'], ['app_user.id'], ondelete='SET NULL', name='fk_consultation_editor'),
        ForeignKeyConstraint(['follow_up_person_id'], ['app_user.id'], ondelete='SET NULL', name='fk_consultation_follow_up_person'),
        PrimaryKeyConstraint('id', name='consultation_pkey'),
        UniqueConstraint('consultation_code', name='consultation_code_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    consultation_code: Mapped[str] = mapped_column(String(50), nullable=False)
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
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


class Translator(Base):
    __tablename__ = 'translator'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='translator_pkey'),
        UniqueConstraint('translator_code', name='translator_translator_code_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    translator_code: Mapped[Optional[str]] = mapped_column(String(50))
    translator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cooperation_type: Mapped[Optional[str]] = mapped_column(String(50))
    contact_info: Mapped[Optional[str]] = mapped_column(String(255))
    translation_type: Mapped[Optional[str]] = mapped_column(String(255))
    quality_score: Mapped[Optional[str]] = mapped_column(String(10))
    cloud_revision: Mapped[Optional[str]] = mapped_column(String(50))
    daily_rate: Mapped[Optional[str]] = mapped_column(String(100))
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
    first_contact_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    projects: Mapped[list['TranslationProject']] = relationship('TranslationProject', back_populates='translator')


class TranslationProject(Base):
    __tablename__ = 'translation_project'
    __table_args__ = (
        ForeignKeyConstraint(['client_id'], ['client.id'], ondelete='RESTRICT', name='fk_translation_project_client'),
        ForeignKeyConstraint(['translator_id'], ['translator.id'], ondelete='SET NULL', name='fk_translation_project_translator'),
        ForeignKeyConstraint(['pm_confirmed_by'], ['app_user.id'], ondelete='SET NULL', name='fk_translation_project_pm'),
        ForeignKeyConstraint(['created_by'], ['app_user.id'], ondelete='SET NULL', name='fk_translation_project_creator'),
        PrimaryKeyConstraint('id', name='translation_project_pkey'),
        UniqueConstraint('order_no', name='translation_project_order_no_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    order_no: Mapped[str] = mapped_column(String(50), nullable=False)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type_secondary: Mapped[Optional[str]] = mapped_column(String(100))
    
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    customer_reception_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    customer_deadline_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    sent_to_client_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    client_feedback: Mapped[Optional[str]] = mapped_column(Text)
    
    language_pair: Mapped[Optional[str]] = mapped_column(String(100))
    priority: Mapped[Optional[str]] = mapped_column(String(50))
    word_count: Mapped[Optional[int]] = mapped_column(BigInteger)
    
    project_status: Mapped[Optional[str]] = mapped_column(String(50))
    pm_confirmed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    
    translator_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    translator_assignment_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    expected_translator_stats_method: Mapped[Optional[str]] = mapped_column(String(100))
    expected_translator_word_count: Mapped[Optional[int]] = mapped_column(BigInteger)
    
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

    # 网络文件路径（如 \\win-server\xxx）
    network_file_path: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    client: Mapped[Optional['Client']] = relationship('Client', back_populates='projects')
    translator: Mapped[Optional['Translator']] = relationship('Translator', back_populates='projects')
    pm_user: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[pm_confirmed_by])
    creator: Mapped[Optional['AppUser']] = relationship('AppUser', foreign_keys=[created_by])
    
    project_file: Mapped[list['ProjectFile']] = relationship('ProjectFile', back_populates='translation_project', cascade='all, delete-orphan')
    workflow_instance: Mapped[Optional['WorkflowInstance']] = relationship('WorkflowInstance', back_populates='translation_project', uselist=False, cascade='all, delete-orphan')
    sub_orders: Mapped[list['TranslationSubOrder']] = relationship('TranslationSubOrder', back_populates='parent_project', cascade='all, delete-orphan')


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
    sub_order_no: Mapped[str] = mapped_column(String(60), nullable=False)  # 如 TP-20260302-0014.0001
    sub_project_name: Mapped[Optional[str]] = mapped_column(String(255))

    # 文件/语言/字数
    file_type_secondary: Mapped[Optional[str]] = mapped_column(String(100))
    language_pair: Mapped[Optional[str]] = mapped_column(String(100))
    priority: Mapped[Optional[str]] = mapped_column(String(50))
    word_count: Mapped[Optional[int]] = mapped_column(BigInteger)

    # 时间节点（子订单独立的时间）
    customer_deadline_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    sent_to_client_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    client_feedback: Mapped[Optional[str]] = mapped_column(Text)

    # 译员信息
    translator_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    translator_assignment_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    expected_translator_stats_method: Mapped[Optional[str]] = mapped_column(String(100))
    expected_translator_word_count: Mapped[Optional[int]] = mapped_column(BigInteger)

    # 各流程进度（与母订单字段一致）
    status: Mapped[Optional[str]] = mapped_column(String(50), server_default=text("'pending'"))
    translator_delivery_progress: Mapped[Optional[str]] = mapped_column(String(20))
    pre_review_qc_progress: Mapped[Optional[str]] = mapped_column(String(20))
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
        ForeignKeyConstraint(['translation_project_id'], ['translation_project.id'], ondelete='CASCADE', name='fk_project_file_project'),
        ForeignKeyConstraint(['uploaded_by'], ['app_user.id'], ondelete='SET NULL', name='fk_uploader'),
        PrimaryKeyConstraint('id', name='project_file_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    translation_project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(50))
    file_ext: Mapped[Optional[str]] = mapped_column(String(20))
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    storage_type: Mapped[Optional[str]] = mapped_column(String(50))
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))

    translation_project: Mapped['TranslationProject'] = relationship('TranslationProject', back_populates='project_file')
    app_user: Mapped[Optional['AppUser']] = relationship('AppUser', back_populates='project_file')


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
        PrimaryKeyConstraint('id', name='employee_leave_pkey'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    employee_name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    leave_type: Mapped[Optional[str]] = mapped_column(String(50))
    reason: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))


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
