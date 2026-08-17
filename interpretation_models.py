"""口译项目独立数据模型。"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import AppUser, Base, Client, Consultation, SubClient, Translator


class InterpretationLanguage(Base):
    __tablename__ = "interpretation_language"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="interpretation_language_pkey"),
        UniqueConstraint("label", name="uq_interpretation_language_label"),
        ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], ondelete="SET NULL",
            name="fk_interpretation_language_creator",
        ),
        ForeignKeyConstraint(
            ["updated_by"], ["app_user.id"], ondelete="SET NULL",
            name="fk_interpretation_language_updater",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    is_custom: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    creator: Mapped[Optional[AppUser]] = relationship(AppUser, foreign_keys=[created_by])
    updater: Mapped[Optional[AppUser]] = relationship(AppUser, foreign_keys=[updated_by])


class InterpretationProject(Base):
    __tablename__ = "interpretation_project"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="interpretation_project_pkey"),
        UniqueConstraint("order_no", name="uq_interpretation_project_order_no"),
        UniqueConstraint("consultation_id", name="uq_interpretation_project_consultation"),
        ForeignKeyConstraint(
            ["consultation_id"], ["consultation.id"], ondelete="SET NULL",
            name="fk_interpretation_project_consultation",
        ),
        ForeignKeyConstraint(
            ["client_id"], ["client.id"], ondelete="RESTRICT",
            name="fk_interpretation_project_client",
        ),
        ForeignKeyConstraint(
            ["sub_client_id"], ["sub_client.id"], ondelete="SET NULL",
            name="fk_interpretation_project_sub_client",
        ),
        ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], ondelete="SET NULL",
            name="fk_interpretation_project_creator",
        ),
        CheckConstraint(
            "required_interpreter_count IS NULL OR required_interpreter_count >= 0",
            name="ck_interpretation_required_interpreter_count",
        ),
        Index("ix_interpretation_project_status", "project_status"),
        Index("ix_interpretation_project_client", "client_id"),
        Index("ix_interpretation_project_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_no: Mapped[str] = mapped_column(String(50), nullable=False)
    project_name: Mapped[Optional[str]] = mapped_column(String(500))
    project_types: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    task_description: Mapped[Optional[str]] = mapped_column(Text)
    consultation_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    sub_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    contact_name: Mapped[Optional[str]] = mapped_column(String(255))
    customer_order_no: Mapped[Optional[str]] = mapped_column(String(150))
    project_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'initial_follow_up'")
    )
    locations: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    customer_budget: Mapped[Optional[str]] = mapped_column(String(500))
    required_interpreter_count: Mapped[Optional[int]] = mapped_column(Integer)
    required_interpreter_gender: Mapped[Optional[str]] = mapped_column(String(20))
    required_interpretation_level: Mapped[Optional[str]] = mapped_column(String(20))
    interpreter_special_requirements: Mapped[Optional[str]] = mapped_column(Text)
    interpreter_height_requirement: Mapped[Optional[str]] = mapped_column(String(100))
    interpreter_appearance_requirement: Mapped[Optional[str]] = mapped_column(String(255))
    interpreter_dress_requirement: Mapped[Optional[str]] = mapped_column(String(255))
    customer_consultation_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    customer_confirmation_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    interpretation_domain: Mapped[Optional[str]] = mapped_column(Text)
    interpretation_content: Mapped[Optional[str]] = mapped_column(Text)
    file_path: Mapped[Optional[str]] = mapped_column(Text)
    quotation_path: Mapped[Optional[str]] = mapped_column(Text)
    contract_path: Mapped[Optional[str]] = mapped_column(Text)
    client_rating: Mapped[Optional[str]] = mapped_column(String(50))
    client_rating_note: Mapped[Optional[str]] = mapped_column(Text)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    email_subject_preview: Mapped[Optional[str]] = mapped_column(Text)
    social_post_request: Mapped[Optional[str]] = mapped_column(Text)
    resource_request: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    consultation: Mapped[Optional[Consultation]] = relationship(Consultation)
    client: Mapped[Optional[Client]] = relationship(Client)
    sub_client: Mapped[Optional[SubClient]] = relationship(SubClient)
    creator: Mapped[Optional[AppUser]] = relationship(AppUser, foreign_keys=[created_by])
    time_ranges: Mapped[list["InterpretationProjectTimeRange"]] = relationship(
        back_populates="project", cascade="all, delete-orphan",
        order_by="InterpretationProjectTimeRange.sequence_no",
    )
    language_directions: Mapped[list["InterpretationProjectLanguageDirection"]] = relationship(
        back_populates="project", cascade="all, delete-orphan",
        order_by="InterpretationProjectLanguageDirection.sequence_no",
    )
    interpreter_assignments: Mapped[list["InterpretationProjectInterpreter"]] = relationship(
        back_populates="project", cascade="all, delete-orphan",
        order_by="InterpretationProjectInterpreter.sequence_no",
    )

    @property
    def client_short_name(self) -> Optional[str]:
        selected = self.sub_client or self.client
        return selected.client_short_name if selected else None

    @property
    def client_code(self) -> Optional[str]:
        if self.sub_client:
            return self.sub_client.sub_client_code
        return self.client.client_code if self.client else None

    @property
    def client_full_name(self) -> Optional[str]:
        selected = self.sub_client or self.client
        return selected.client_name if selected else None

    @property
    def client_domain(self) -> Optional[str]:
        selected = self.sub_client or self.client
        if not selected:
            return None
        values = [selected.field_level1, selected.field_level2]
        return " / ".join(value for value in values if value) or None

    @property
    def current_client_manager(self) -> Optional[str]:
        selected = self.sub_client or self.client
        return selected.client_manager if selected else None

    @property
    def sub_client_contact(self) -> Optional[str]:
        values = []
        if self.sub_client:
            values.append(self.sub_client.client_short_name)
        if self.contact_name:
            values.append(self.contact_name)
        return " / ".join(values) or None

    @property
    def language_directions_display(self) -> Optional[str]:
        values = [item.display for item in self.language_directions]
        return "；".join(value for value in values if value) or None

    @property
    def assigned_interpreters_display(self) -> Optional[str]:
        values = [item.translator_name for item in self.interpreter_assignments]
        return "；".join(value for value in values if value) or None

    @property
    def translator_codes(self) -> Optional[str]:
        values = [item.translator_code for item in self.interpreter_assignments]
        return "；".join(value for value in values if value) or None


class InterpretationProjectTimeRange(Base):
    __tablename__ = "interpretation_project_time_range"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="interpretation_project_time_range_pkey"),
        ForeignKeyConstraint(
            ["project_id"], ["interpretation_project.id"], ondelete="CASCADE",
            name="fk_interpretation_time_range_project",
        ),
        UniqueConstraint("project_id", "sequence_no", name="uq_interpretation_time_range_sequence"),
        CheckConstraint("scheduled_end >= scheduled_start", name="ck_interpretation_scheduled_range"),
        CheckConstraint(
            "actual_end IS NULL OR (actual_start IS NOT NULL AND actual_end >= actual_start)",
            name="ck_interpretation_actual_range",
        ),
        Index("ix_interpretation_time_range_scheduled", "scheduled_start", "scheduled_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_start: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    scheduled_end: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    actual_start: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    actual_end: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    project: Mapped[InterpretationProject] = relationship(back_populates="time_ranges")


class InterpretationProjectLanguageDirection(Base):
    __tablename__ = "interpretation_project_language_direction"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="interpretation_project_language_direction_pkey"),
        ForeignKeyConstraint(
            ["project_id"], ["interpretation_project.id"], ondelete="CASCADE",
            name="fk_interpretation_direction_project",
        ),
        ForeignKeyConstraint(
            ["source_language_id"], ["interpretation_language.id"], ondelete="RESTRICT",
            name="fk_interpretation_direction_source",
        ),
        ForeignKeyConstraint(
            ["target_language_id"], ["interpretation_language.id"], ondelete="RESTRICT",
            name="fk_interpretation_direction_target",
        ),
        UniqueConstraint("project_id", "sequence_no", name="uq_interpretation_direction_sequence"),
        CheckConstraint("source_language_id <> target_language_id", name="ck_interpretation_direction_distinct"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_language_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    target_language_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    project: Mapped[InterpretationProject] = relationship(back_populates="language_directions")
    source_language: Mapped[InterpretationLanguage] = relationship(
        InterpretationLanguage, foreign_keys=[source_language_id]
    )
    target_language: Mapped[InterpretationLanguage] = relationship(
        InterpretationLanguage, foreign_keys=[target_language_id]
    )

    @property
    def source_language_label(self) -> str:
        return self.source_language.label

    @property
    def target_language_label(self) -> str:
        return self.target_language.label

    @property
    def display(self) -> str:
        return f"{self.source_language_label} ↔ {self.target_language_label}"


class InterpretationProjectInterpreter(Base):
    __tablename__ = "interpretation_project_interpreter"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="interpretation_project_interpreter_pkey"),
        ForeignKeyConstraint(
            ["project_id"], ["interpretation_project.id"], ondelete="CASCADE",
            name="fk_interpretation_interpreter_project",
        ),
        ForeignKeyConstraint(
            ["translator_id"], ["translator.id"], ondelete="RESTRICT",
            name="fk_interpretation_interpreter_translator",
        ),
        UniqueConstraint("project_id", "translator_id", name="uq_interpretation_project_translator"),
        UniqueConstraint("project_id", "sequence_no", name="uq_interpretation_interpreter_sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    translator_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_rating: Mapped[Optional[str]] = mapped_column(String(50))
    evaluation_note: Mapped[Optional[str]] = mapped_column(Text)

    project: Mapped[InterpretationProject] = relationship(back_populates="interpreter_assignments")
    translator: Mapped[Translator] = relationship(Translator)

    @property
    def translator_name(self) -> str:
        return self.translator.translator_name

    @property
    def translator_code(self) -> Optional[str]:
        return self.translator.translator_code

    @property
    def translator_gender(self) -> Optional[str]:
        return self.translator.gender

    @property
    def translator_height(self) -> Optional[str]:
        return self.translator.height

    @property
    def translator_appearance(self) -> Optional[str]:
        return self.translator.appearance

    @property
    def translator_interpretation_level(self) -> Optional[str]:
        return self.translator.interpretation_level

    @property
    def translator_languages(self) -> Optional[str]:
        return self.translator.languages

    @property
    def translator_translation_type(self) -> Optional[str]:
        return self.translator.translation_type

    @property
    def translator_direction(self) -> Optional[str]:
        return self.translator.direction

    @property
    def translator_resume_path(self) -> Optional[str]:
        return self.translator.resume_path
