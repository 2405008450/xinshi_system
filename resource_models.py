"""统一人才资源库数据库模型。"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


CAPABILITY_TYPES = ("written_translation", "interpretation", "annotation")
RESOURCE_STATUSES = ("active", "standby", "inactive")


class ResourcePerson(Base):
    __tablename__ = "resource_person"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="resource_person_pkey"),
        UniqueConstraint("resource_code", name="uq_resource_person_code"),
        UniqueConstraint("idempotency_key", name="uq_resource_person_idempotency_key"),
        CheckConstraint(
            "status IN ('active', 'standby', 'inactive')",
            name="ck_resource_person_status",
        ),
        Index("ix_resource_person_name", "full_name"),
        Index("ix_resource_person_primary_phone", "primary_phone"),
        Index("ix_resource_person_primary_email", "primary_email"),
        Index("ix_resource_person_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128))
    resource_code: Mapped[Optional[str]] = mapped_column(String(50))
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cooperation_type: Mapped[Optional[str]] = mapped_column(String(50))
    contact_info: Mapped[Optional[str]] = mapped_column(String(500))
    primary_phone: Mapped[Optional[str]] = mapped_column(String(50))
    secondary_phone: Mapped[Optional[str]] = mapped_column(String(50))
    primary_email: Mapped[Optional[str]] = mapped_column(String(255))
    secondary_email: Mapped[Optional[str]] = mapped_column(String(255))
    other_contact: Mapped[Optional[str]] = mapped_column(String(255))
    resume_path: Mapped[Optional[str]] = mapped_column(Text)
    gender: Mapped[Optional[str]] = mapped_column(String(20))
    birth_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    native_place: Mapped[Optional[str]] = mapped_column(String(255))
    residence_address: Mapped[Optional[str]] = mapped_column(String(500))
    dialects: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    dialect_regions: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    height: Mapped[Optional[str]] = mapped_column(String(50))
    appearance: Mapped[Optional[str]] = mapped_column(String(255))
    nationality: Mapped[Optional[str]] = mapped_column(String(100))
    ethnicity: Mapped[Optional[str]] = mapped_column(String(100))
    overall_rating: Mapped[Optional[str]] = mapped_column(Text)
    first_contact_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'standby'")
    )
    duplicate_review_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    capabilities: Mapped[list["ResourceCapability"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    written_profile: Mapped[Optional["WrittenTranslationProfile"]] = relationship(
        back_populates="person", cascade="all, delete-orphan", uselist=False
    )
    interpretation_profile: Mapped[Optional["InterpretationProfile"]] = relationship(
        back_populates="person", cascade="all, delete-orphan", uselist=False
    )
    annotation_profile: Mapped[Optional["AnnotationProfile"]] = relationship(
        back_populates="person", cascade="all, delete-orphan", uselist=False
    )
    annotation_language_skills: Mapped[list["ResourceAnnotationLanguageSkill"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    career_profile: Mapped[Optional["ResourceCareerProfile"]] = relationship(
        back_populates="person", cascade="all, delete-orphan", uselist=False
    )

    @property
    def capability_types(self) -> list[str]:
        return [item.capability_type for item in self.capabilities if item.status != "inactive"]

    @property
    def language_directions(self) -> list[str]:
        """汇总笔译和口译语种，供人才列表快速识别。"""
        values = []
        for profile in (self.written_profile, self.interpretation_profile):
            value = profile.languages if profile else None
            if value and value not in values:
                values.append(value)
        return values

    @property
    def annotation_language_directions(self) -> list[str]:
        return [item.display for item in self.annotation_language_skills]

    @property
    def industries(self) -> list[str]:
        return list(self.career_profile.industries or []) if self.career_profile else []

    @property
    def job_titles(self) -> list[str]:
        return list(self.career_profile.job_titles or []) if self.career_profile else []

    @property
    def years_experience(self) -> Optional[Decimal]:
        return self.career_profile.years_experience if self.career_profile else None


class ResourceCapability(Base):
    __tablename__ = "resource_capability"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="resource_capability_pkey"),
        ForeignKeyConstraint(
            ["person_id"], ["resource_person.id"], ondelete="CASCADE",
            name="fk_resource_capability_person",
        ),
        UniqueConstraint("person_id", "capability_type", name="uq_resource_person_capability"),
        CheckConstraint(
            "capability_type IN ('written_translation', 'interpretation', 'annotation')",
            name="ck_resource_capability_type",
        ),
        CheckConstraint(
            "status IN ('active', 'standby', 'inactive')",
            name="ck_resource_capability_status",
        ),
        Index("ix_resource_capability_type_status", "capability_type", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    person_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    capability_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
    )
    review_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'manual'")
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    person: Mapped[ResourcePerson] = relationship(back_populates="capabilities")


class WrittenTranslationProfile(Base):
    __tablename__ = "resource_written_translation_profile"
    __table_args__ = (
        PrimaryKeyConstraint("person_id", name="resource_written_profile_pkey"),
        ForeignKeyConstraint(
            ["person_id"], ["resource_person.id"], ondelete="CASCADE",
            name="fk_resource_written_profile_person",
        ),
    )

    person_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    languages: Mapped[Optional[str]] = mapped_column(String(500))
    direction: Mapped[Optional[str]] = mapped_column(String(50))
    domain_skills: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    quality_score: Mapped[Optional[str]] = mapped_column(String(50))
    default_priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    daily_accept_count: Mapped[Optional[int]] = mapped_column(Integer)
    hourly_speed: Mapped[Optional[int]] = mapped_column(Integer)
    daily_word_capacity: Mapped[Optional[int]] = mapped_column(Integer)
    can_cloud_edit: Mapped[Optional[bool]] = mapped_column(Boolean)
    can_revision: Mapped[Optional[bool]] = mapped_column(Boolean)
    available_time_slot: Mapped[Optional[str]] = mapped_column(String(100))
    schedule_remarks: Mapped[Optional[str]] = mapped_column(Text)
    availability_updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    person: Mapped[ResourcePerson] = relationship(back_populates="written_profile")


class InterpretationProfile(Base):
    __tablename__ = "resource_interpretation_profile"
    __table_args__ = (
        PrimaryKeyConstraint("person_id", name="resource_interpretation_profile_pkey"),
        ForeignKeyConstraint(
            ["person_id"], ["resource_person.id"], ondelete="CASCADE",
            name="fk_resource_interpretation_profile_person",
        ),
    )

    person_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    languages: Mapped[Optional[str]] = mapped_column(String(500))
    direction: Mapped[Optional[str]] = mapped_column(String(50))
    interpretation_level: Mapped[Optional[str]] = mapped_column(String(20))
    interpretation_modes: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    domain_skills: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    quality_score: Mapped[Optional[str]] = mapped_column(String(50))
    evaluation_summary: Mapped[Optional[str]] = mapped_column(Text)

    person: Mapped[ResourcePerson] = relationship(back_populates="interpretation_profile")


class AnnotationProfile(Base):
    __tablename__ = "resource_annotation_profile"
    __table_args__ = (
        PrimaryKeyConstraint("person_id", name="resource_annotation_profile_pkey"),
        ForeignKeyConstraint(
            ["person_id"], ["resource_person.id"], ondelete="CASCADE",
            name="fk_resource_annotation_profile_person",
        ),
    )

    person_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    task_types: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    data_modalities: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    tools: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    domain_skills: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    quality_score: Mapped[Optional[str]] = mapped_column(String(50))
    daily_capacity: Mapped[Optional[int]] = mapped_column(Integer)
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    person: Mapped[ResourcePerson] = relationship(back_populates="annotation_profile")


class ResourceAnnotationLanguageSkill(Base):
    """标注员可承接的单语/方言或双语方向。"""

    __tablename__ = "resource_annotation_language_skill"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="resource_annotation_language_skill_pkey"),
        ForeignKeyConstraint(
            ["person_id"], ["resource_person.id"], ondelete="CASCADE",
            name="fk_resource_annotation_language_person",
        ),
        ForeignKeyConstraint(
            ["source_language_id"], ["interpretation_language.id"], ondelete="RESTRICT",
            name="fk_resource_annotation_language_source",
        ),
        ForeignKeyConstraint(
            ["target_language_id"], ["interpretation_language.id"], ondelete="RESTRICT",
            name="fk_resource_annotation_language_target",
        ),
        CheckConstraint(
            "target_language_id IS NULL OR source_language_id <> target_language_id",
            name="ck_resource_annotation_language_distinct",
        ),
        Index(
            "uq_resource_annotation_language_single", "person_id", "source_language_id",
            unique=True, postgresql_where=text("target_language_id IS NULL"),
            sqlite_where=text("target_language_id IS NULL"),
        ),
        Index(
            "uq_resource_annotation_language_pair", "person_id", "source_language_id",
            "target_language_id", unique=True,
            postgresql_where=text("target_language_id IS NOT NULL"),
            sqlite_where=text("target_language_id IS NOT NULL"),
        ),
        Index("ix_resource_annotation_language_person", "person_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    person_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_language_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    target_language_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    person: Mapped[ResourcePerson] = relationship(back_populates="annotation_language_skills")
    source_language = relationship("InterpretationLanguage", foreign_keys=[source_language_id])
    target_language = relationship("InterpretationLanguage", foreign_keys=[target_language_id])

    @property
    def source_language_label(self) -> str:
        return self.source_language.label

    @property
    def target_language_label(self) -> Optional[str]:
        return self.target_language.label if self.target_language else None

    @property
    def display(self) -> str:
        if self.target_language_label:
            return f"{self.source_language_label}→{self.target_language_label}"
        return self.source_language_label


class ResourceCareerProfile(Base):
    __tablename__ = "resource_career_profile"
    __table_args__ = (
        PrimaryKeyConstraint("person_id", name="resource_career_profile_pkey"),
        ForeignKeyConstraint(
            ["person_id"], ["resource_person.id"], ondelete="CASCADE",
            name="fk_resource_career_profile_person",
        ),
    )

    person_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    industries: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    functions: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    job_titles: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    years_experience: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    preferred_locations: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    expected_salary: Mapped[Optional[str]] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(Text)

    person: Mapped[ResourcePerson] = relationship(back_populates="career_profile")
