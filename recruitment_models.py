"""招聘项目数据模型。"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from interpretation_models import InterpretationLanguage
from models import AppUser, Base, Client, Consultation, SubClient
from resource_models import ResourcePerson


class RecruitmentProject(Base):
    __tablename__ = "recruitment_project"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="recruitment_project_pkey"),
        UniqueConstraint("order_no", name="uq_recruitment_project_order_no"),
        UniqueConstraint("consultation_id", name="uq_recruitment_project_consultation"),
        ForeignKeyConstraint(["consultation_id"], ["consultation.id"], ondelete="SET NULL", name="fk_recruitment_project_consultation"),
        ForeignKeyConstraint(["client_id"], ["client.id"], ondelete="RESTRICT", name="fk_recruitment_project_client"),
        ForeignKeyConstraint(["sub_client_id"], ["sub_client.id"], ondelete="SET NULL", name="fk_recruitment_project_sub_client"),
        ForeignKeyConstraint(["client_manager_id"], ["app_user.id"], ondelete="SET NULL", name="fk_recruitment_project_client_manager"),
        ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL", name="fk_recruitment_project_creator"),
        CheckConstraint("headcount_min IS NULL OR headcount_min >= 0", name="ck_recruitment_headcount_min"),
        CheckConstraint("headcount_max IS NULL OR headcount_max >= headcount_min", name="ck_recruitment_headcount_range"),
        CheckConstraint("employment_end IS NULL OR employment_start IS NULL OR employment_end >= employment_start", name="ck_recruitment_employment_range"),
        CheckConstraint("service_fee_rate IS NULL OR (service_fee_rate >= 0 AND service_fee_rate <= 100)", name="ck_recruitment_service_fee_rate"),
        Index("ix_recruitment_project_status", "project_status"),
        Index("ix_recruitment_project_client", "client_id"),
        Index("ix_recruitment_project_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    order_no: Mapped[str] = mapped_column(String(50), nullable=False)
    project_name: Mapped[Optional[str]] = mapped_column(String(500))
    job_description: Mapped[Optional[str]] = mapped_column(Text)
    position_title: Mapped[Optional[str]] = mapped_column(String(255))
    headcount_min: Mapped[Optional[int]] = mapped_column(Integer)
    headcount_max: Mapped[Optional[int]] = mapped_column(Integer)
    project_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'pending_setup'"))

    consultation_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    sub_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    contact_name: Mapped[Optional[str]] = mapped_column(String(255))
    customer_order_no: Mapped[Optional[str]] = mapped_column(String(150))
    client_manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    client_manager_name_snapshot: Mapped[Optional[str]] = mapped_column(String(255))

    target_onboard_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'date'"))
    target_onboard_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    employment_start: Mapped[Optional[datetime.date]] = mapped_column(Date)
    employment_end: Mapped[Optional[datetime.date]] = mapped_column(Date)
    work_location: Mapped[Optional[str]] = mapped_column(String(500))

    service_fee_type: Mapped[Optional[str]] = mapped_column(String(30))
    service_fee_currency: Mapped[Optional[str]] = mapped_column(String(10), server_default=text("'CNY'"))
    service_fee_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    service_fee_rate: Mapped[Optional[float]] = mapped_column(Numeric(7, 4))
    service_fee_note: Mapped[Optional[str]] = mapped_column(Text)

    customer_consultation_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    customer_confirmation_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    project_path: Mapped[Optional[str]] = mapped_column(Text)
    quotation_path: Mapped[Optional[str]] = mapped_column(Text)
    contract_path: Mapped[Optional[str]] = mapped_column(Text)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    email_subject_preview: Mapped[Optional[str]] = mapped_column(Text)
    social_post_request: Mapped[Optional[str]] = mapped_column(Text)
    resource_request: Mapped[Optional[str]] = mapped_column(Text)

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    consultation: Mapped[Optional[Consultation]] = relationship(Consultation)
    client: Mapped[Optional[Client]] = relationship(Client)
    sub_client: Mapped[Optional[SubClient]] = relationship(SubClient)
    client_manager: Mapped[Optional[AppUser]] = relationship(AppUser, foreign_keys=[client_manager_id])
    creator: Mapped[Optional[AppUser]] = relationship(AppUser, foreign_keys=[created_by])
    language_directions: Mapped[list["RecruitmentProjectLanguageDirection"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="RecruitmentProjectLanguageDirection.sequence_no"
    )
    progress_records: Mapped[list["RecruitmentProjectProgress"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="RecruitmentProjectProgress.occurred_at"
    )
    candidates: Mapped[list["RecruitmentCandidate"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="RecruitmentCandidate.created_at"
    )

    @property
    def client_short_name(self):
        return self.sub_client.client_short_name if self.sub_client else (self.client.client_short_name if self.client else None)

    @property
    def client_code(self):
        return self.sub_client.sub_client_code if self.sub_client else (self.client.client_code if self.client else None)

    @property
    def client_name(self):
        return self.sub_client.client_name if self.sub_client else (self.client.client_name if self.client else None)

    @property
    def client_domain(self):
        source = self.sub_client or self.client
        if not source:
            return None
        return " / ".join(value for value in (source.field_level1, source.field_level2) if value) or None

    @property
    def client_manager_name(self):
        return (self.client_manager.full_name or self.client_manager.username) if self.client_manager else self.client_manager_name_snapshot

    @property
    def candidate_count(self):
        return len(self.candidates or [])


class RecruitmentResumeSource(Base):
    __tablename__ = "recruitment_resume_source"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="recruitment_resume_source_pkey"),
        UniqueConstraint("label", name="uq_recruitment_resume_source_label"),
        ForeignKeyConstraint(["created_by"], ["app_user.id"], ondelete="SET NULL", name="fk_recruitment_resume_source_creator"),
        Index("uq_recruitment_resume_source_label_normalized", text("lower(trim(label))"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class RecruitmentProjectLanguageDirection(Base):
    __tablename__ = "recruitment_project_language_direction"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="recruitment_project_language_direction_pkey"),
        UniqueConstraint("project_id", "sequence_no", name="uq_recruitment_direction_sequence"),
        ForeignKeyConstraint(["project_id"], ["recruitment_project.id"], ondelete="CASCADE", name="fk_recruitment_direction_project"),
        ForeignKeyConstraint(["source_language_id"], ["interpretation_language.id"], ondelete="RESTRICT", name="fk_recruitment_direction_source"),
        ForeignKeyConstraint(["target_language_id"], ["interpretation_language.id"], ondelete="RESTRICT", name="fk_recruitment_direction_target"),
        CheckConstraint("direction_type IN ('single', 'translation')", name="ck_recruitment_direction_type"),
        CheckConstraint("direction_type = 'single' OR target_language_id IS NOT NULL", name="ck_recruitment_direction_target_required"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    direction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_language_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    target_language_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    project: Mapped[RecruitmentProject] = relationship(RecruitmentProject, back_populates="language_directions")
    source_language: Mapped[InterpretationLanguage] = relationship(InterpretationLanguage, foreign_keys=[source_language_id])
    target_language: Mapped[Optional[InterpretationLanguage]] = relationship(InterpretationLanguage, foreign_keys=[target_language_id])

    @property
    def label(self):
        if self.direction_type == "single" or not self.target_language:
            return self.source_language.label
        return f"{self.source_language.label}翻译成{self.target_language.label}"

    @property
    def source_language_label(self):
        return self.source_language.label

    @property
    def target_language_label(self):
        return self.target_language.label if self.target_language else None


class RecruitmentProjectProgress(Base):
    __tablename__ = "recruitment_project_progress"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="recruitment_project_progress_pkey"),
        ForeignKeyConstraint(["project_id"], ["recruitment_project.id"], ondelete="CASCADE", name="fk_recruitment_progress_project"),
        ForeignKeyConstraint(["operator_id"], ["app_user.id"], ondelete="SET NULL", name="fk_recruitment_progress_operator"),
        Index("ix_recruitment_progress_project_time", "project_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(50))
    to_status: Mapped[Optional[str]] = mapped_column(String(50))
    note: Mapped[Optional[str]] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    operator_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    occurred_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    project: Mapped[RecruitmentProject] = relationship(RecruitmentProject, back_populates="progress_records")
    operator: Mapped[Optional[AppUser]] = relationship(AppUser, foreign_keys=[operator_id])

    @property
    def operator_name(self):
        return (self.operator.full_name or self.operator.username) if self.operator else None


class RecruitmentCandidate(Base):
    __tablename__ = "recruitment_candidate"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="recruitment_candidate_pkey"),
        ForeignKeyConstraint(["project_id"], ["recruitment_project.id"], ondelete="CASCADE", name="fk_recruitment_candidate_project"),
        ForeignKeyConstraint(["person_id"], ["resource_person.id"], ondelete="RESTRICT", name="fk_recruitment_candidate_person"),
        ForeignKeyConstraint(["owner_id"], ["app_user.id"], ondelete="SET NULL", name="fk_recruitment_candidate_owner"),
        ForeignKeyConstraint(["resume_source_id"], ["recruitment_resume_source.id"], ondelete="SET NULL", name="fk_recruitment_candidate_resume_source"),
        Index("ix_recruitment_candidate_project", "project_id"),
        Index("ix_recruitment_candidate_person", "person_id"),
        Index("ix_recruitment_candidate_stage", "stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    person_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_info: Mapped[Optional[str]] = mapped_column(String(500))
    resume_path: Mapped[Optional[str]] = mapped_column(Text)
    resume_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'screening'"))
    recommended_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    interview_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    offer_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    planned_onboard_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    actual_onboard_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    first_interview_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    first_interview_details: Mapped[Optional[str]] = mapped_column(Text)
    second_interview_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    second_interview_details: Mapped[Optional[str]] = mapped_column(Text)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    next_follow_up_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    project: Mapped[RecruitmentProject] = relationship(RecruitmentProject, back_populates="candidates")
    person: Mapped[Optional[ResourcePerson]] = relationship(ResourcePerson)
    owner: Mapped[Optional[AppUser]] = relationship(AppUser, foreign_keys=[owner_id])
    resume_source: Mapped[Optional[RecruitmentResumeSource]] = relationship(RecruitmentResumeSource)
    communications: Mapped[list["RecruitmentCandidateCommunication"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan",
        order_by="RecruitmentCandidateCommunication.sequence_no",
    )
    interviews: Mapped[list["RecruitmentCandidateInterview"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan",
        order_by="RecruitmentCandidateInterview.round_no",
    )

    @property
    def owner_name(self):
        return (self.owner.full_name or self.owner.username) if self.owner else None

    @property
    def resume_source_label(self):
        return self.resume_source.label if self.resume_source else None


class RecruitmentCandidateCommunication(Base):
    __tablename__ = "recruitment_candidate_communication"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="recruitment_candidate_communication_pkey"),
        UniqueConstraint("candidate_id", "sequence_no", name="uq_recruitment_candidate_communication_sequence"),
        ForeignKeyConstraint(
            ["candidate_id"], ["recruitment_candidate.id"], ondelete="CASCADE",
            name="fk_recruitment_candidate_communication_candidate",
        ),
        CheckConstraint("sequence_no > 0", name="ck_recruitment_candidate_communication_sequence"),
        Index("ix_recruitment_candidate_communication_candidate", "candidate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    communication_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    candidate: Mapped[RecruitmentCandidate] = relationship(RecruitmentCandidate, back_populates="communications")


class RecruitmentCandidateInterview(Base):
    __tablename__ = "recruitment_candidate_interview"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="recruitment_candidate_interview_pkey"),
        UniqueConstraint("candidate_id", "round_no", name="uq_recruitment_candidate_interview_round"),
        ForeignKeyConstraint(
            ["candidate_id"], ["recruitment_candidate.id"], ondelete="CASCADE",
            name="fk_recruitment_candidate_interview_candidate",
        ),
        CheckConstraint("round_no > 0", name="ck_recruitment_candidate_interview_round"),
        Index("ix_recruitment_candidate_interview_candidate", "candidate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    interview_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    candidate: Mapped[RecruitmentCandidate] = relationship(RecruitmentCandidate, back_populates="interviews")
