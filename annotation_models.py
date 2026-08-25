"""标注项目数据库模型。"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
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

from interpretation_models import InterpretationLanguage
from models import AppUser, Base, Client, Consultation, SubClient, TranslationProject
from resource_models import ResourcePerson


class AnnotationProject(Base):
    __tablename__ = "annotation_project"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_project_pkey"),
        UniqueConstraint("order_no", name="uq_annotation_project_order_no"),
        UniqueConstraint("consultation_id", name="uq_annotation_project_consultation"),
        UniqueConstraint(
            "legacy_translation_project_id",
            name="uq_annotation_project_legacy_translation",
        ),
        ForeignKeyConstraint(
            ["consultation_id"], ["consultation.id"], ondelete="SET NULL",
            name="fk_annotation_project_consultation",
        ),
        ForeignKeyConstraint(
            ["client_id"], ["client.id"], ondelete="RESTRICT",
            name="fk_annotation_project_client",
        ),
        ForeignKeyConstraint(
            ["sub_client_id"], ["sub_client.id"], ondelete="SET NULL",
            name="fk_annotation_project_sub_client",
        ),
        ForeignKeyConstraint(
            ["client_manager_id"], ["app_user.id"], ondelete="SET NULL",
            name="fk_annotation_project_client_manager",
        ),
        ForeignKeyConstraint(
            ["created_by"], ["app_user.id"], ondelete="SET NULL",
            name="fk_annotation_project_creator",
        ),
        ForeignKeyConstraint(
            ["legacy_translation_project_id"], ["translation_project.id"],
            ondelete="SET NULL", name="fk_annotation_project_legacy_translation",
        ),
        CheckConstraint(
            "task_submitted_at IS NULL OR task_dispatched_at IS NULL "
            "OR task_submitted_at >= task_dispatched_at",
            name="ck_annotation_project_task_times",
        ),
        Index("ix_annotation_project_status", "project_status"),
        Index("ix_annotation_project_client", "client_id"),
        Index("ix_annotation_project_client_manager", "client_manager_id"),
        Index("ix_annotation_project_created_at", "created_at"),
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
    email_subject_preview: Mapped[Optional[str]] = mapped_column(String(1000))
    project_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'pending_confirmation'")
    )
    potential_demand: Mapped[Optional[str]] = mapped_column(Text)
    project_path: Mapped[Optional[str]] = mapped_column(Text)
    quotation_path: Mapped[Optional[str]] = mapped_column(Text)
    contract_path: Mapped[Optional[str]] = mapped_column(Text)
    task_dispatched_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    task_submitted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    client_manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    customer_consultation_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    customer_confirmation_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    legacy_translation_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    legacy_order_no: Mapped[Optional[str]] = mapped_column(String(50))
    legacy_status: Mapped[Optional[str]] = mapped_column(String(50))
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
    client_manager: Mapped[Optional[AppUser]] = relationship(
        AppUser, foreign_keys=[client_manager_id]
    )
    creator: Mapped[Optional[AppUser]] = relationship(
        AppUser, foreign_keys=[created_by]
    )
    legacy_translation_project: Mapped[Optional[TranslationProject]] = relationship(
        TranslationProject, foreign_keys=[legacy_translation_project_id]
    )
    language_items: Mapped[list["AnnotationProjectLanguageItem"]] = relationship(
        back_populates="project", cascade="all, delete-orphan",
        order_by="AnnotationProjectLanguageItem.sequence_no",
    )
    price_items: Mapped[list["AnnotationProjectPriceItem"]] = relationship(
        back_populates="project", cascade="all, delete-orphan",
        order_by="AnnotationProjectPriceItem.sequence_no",
    )
    assignees: Mapped[list["AnnotationProjectAssignee"]] = relationship(
        back_populates="project", cascade="all, delete-orphan",
        order_by="AnnotationProjectAssignee.sequence_no",
    )
    workbench_responsibilities = relationship(
        "ProjectWorkbenchResponsibility",
        back_populates="annotation_project",
        cascade="all, delete-orphan",
    )

    @property
    def role_assignments(self) -> list[dict]:
        from project_roles import PROJECT_ROLE_DEFINITIONS
        by_role = {item.role_code: item for item in (self.workbench_responsibilities or [])}
        return [
            {
                "role_code": definition["role_code"],
                "role_name": definition["role_name"],
                "assignee_id": by_role.get(definition["role_code"]).assignee_id if by_role.get(definition["role_code"]) else None,
                "assignee_name": (
                    (by_role[definition["role_code"]].assignee.full_name or by_role[definition["role_code"]].assignee.username)
                    if by_role.get(definition["role_code"]) and by_role[definition["role_code"]].assignee else None
                ),
                "assignment_type": "direct" if by_role.get(definition["role_code"]) and by_role[definition["role_code"]].assignee_id else "role_pool",
            }
            for definition in PROJECT_ROLE_DEFINITIONS
            if definition["role_code"] in {"project_manager", "project_specialist", "project_assistant"}
        ]

    @property
    def selected_client(self):
        return self.sub_client or self.client

    @property
    def client_short_name(self) -> Optional[str]:
        return self.selected_client.client_short_name if self.selected_client else None

    @property
    def client_code(self) -> Optional[str]:
        if self.sub_client:
            return self.sub_client.sub_client_code
        return self.client.client_code if self.client else None

    @property
    def client_full_name(self) -> Optional[str]:
        return self.selected_client.client_name if self.selected_client else None

    @property
    def client_manager_name(self) -> Optional[str]:
        if not self.client_manager:
            return None
        return self.client_manager.full_name or self.client_manager.username

    @property
    def created_by_name(self) -> Optional[str]:
        if not self.creator:
            return None
        return self.creator.full_name or self.creator.username

    @property
    def consultation_code(self) -> Optional[str]:
        return self.consultation.consultation_code if self.consultation else None

    @property
    def sub_client_contact(self) -> Optional[str]:
        values = []
        if self.sub_client:
            values.append(self.sub_client.client_short_name)
        if self.contact_name:
            values.append(self.contact_name)
        return " / ".join(values) or None

    @property
    def language_items_display(self) -> Optional[str]:
        values = [item.display for item in self.language_items]
        return "；".join(value for value in values if value) or None

    @property
    def customer_price_summary(self) -> Optional[str]:
        values = [item.amount_display for item in self.price_items]
        return "；".join(value for value in values if value) or None

    @property
    def assignee_summary(self) -> Optional[str]:
        status_labels = {
            "assigned": "已安排",
            "in_progress": "进行中",
            "completed": "已完成",
            "cancelled": "已取消",
        }
        values = [
            f"{item.person_name}（{status_labels.get(item.assignment_status, item.assignment_status)}）"
            for item in self.assignees
        ]
        return "；".join(values) or None


class AnnotationProjectAssignee(Base):
    __tablename__ = "annotation_project_assignee"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_project_assignee_pkey"),
        ForeignKeyConstraint(
            ["project_id"], ["annotation_project.id"], ondelete="CASCADE",
            name="fk_annotation_assignee_project",
        ),
        ForeignKeyConstraint(
            ["person_id"], ["resource_person.id"], ondelete="RESTRICT",
            name="fk_annotation_assignee_person",
        ),
        UniqueConstraint("project_id", "person_id", name="uq_annotation_project_assignee"),
        UniqueConstraint("project_id", "sequence_no", name="uq_annotation_assignee_sequence"),
        Index("ix_annotation_assignee_person", "person_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    person_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    assignment_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'assigned'")
    )
    quality_score: Mapped[Optional[str]] = mapped_column(String(50))
    evaluation_note: Mapped[Optional[str]] = mapped_column(Text)

    project: Mapped[AnnotationProject] = relationship(back_populates="assignees")
    person: Mapped[ResourcePerson] = relationship(ResourcePerson)

    @property
    def person_name(self) -> str:
        return self.person.full_name

    @property
    def resource_code(self) -> Optional[str]:
        return self.person.resource_code


class AnnotationProjectLanguageItem(Base):
    __tablename__ = "annotation_project_language_item"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_project_language_item_pkey"),
        ForeignKeyConstraint(
            ["project_id"], ["annotation_project.id"], ondelete="CASCADE",
            name="fk_annotation_language_item_project",
        ),
        ForeignKeyConstraint(
            ["source_language_id"], ["interpretation_language.id"], ondelete="RESTRICT",
            name="fk_annotation_language_item_source",
        ),
        ForeignKeyConstraint(
            ["target_language_id"], ["interpretation_language.id"], ondelete="RESTRICT",
            name="fk_annotation_language_item_target",
        ),
        UniqueConstraint(
            "project_id", "sequence_no", name="uq_annotation_language_item_sequence"
        ),
        CheckConstraint(
            "target_language_id IS NULL OR source_language_id <> target_language_id",
            name="ck_annotation_language_item_distinct",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_language_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    target_language_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    project: Mapped[AnnotationProject] = relationship(back_populates="language_items")
    source_language: Mapped[InterpretationLanguage] = relationship(
        InterpretationLanguage, foreign_keys=[source_language_id]
    )
    target_language: Mapped[Optional[InterpretationLanguage]] = relationship(
        InterpretationLanguage, foreign_keys=[target_language_id]
    )

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


class AnnotationProjectPriceItem(Base):
    __tablename__ = "annotation_project_price_item"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="annotation_project_price_item_pkey"),
        ForeignKeyConstraint(
            ["project_id"], ["annotation_project.id"], ondelete="CASCADE",
            name="fk_annotation_price_item_project",
        ),
        ForeignKeyConstraint(
            ["source_language_id"], ["interpretation_language.id"], ondelete="RESTRICT",
            name="fk_annotation_price_item_source",
        ),
        ForeignKeyConstraint(
            ["target_language_id"], ["interpretation_language.id"], ondelete="RESTRICT",
            name="fk_annotation_price_item_target",
        ),
        UniqueConstraint(
            "project_id", "sequence_no", name="uq_annotation_price_item_sequence"
        ),
        CheckConstraint("amount > 0", name="ck_annotation_price_item_amount"),
        CheckConstraint(
            "target_language_id IS NULL OR source_language_id IS NOT NULL",
            name="ck_annotation_price_item_language_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    project_type: Mapped[Optional[str]] = mapped_column(String(50))
    source_language_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    target_language_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[Optional[str]] = mapped_column(String(3))
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    project: Mapped[AnnotationProject] = relationship(back_populates="price_items")
    source_language: Mapped[Optional[InterpretationLanguage]] = relationship(
        InterpretationLanguage, foreign_keys=[source_language_id]
    )
    target_language: Mapped[Optional[InterpretationLanguage]] = relationship(
        InterpretationLanguage, foreign_keys=[target_language_id]
    )

    @property
    def source_language_label(self) -> Optional[str]:
        return self.source_language.label if self.source_language else None

    @property
    def target_language_label(self) -> Optional[str]:
        return self.target_language.label if self.target_language else None

    @property
    def language_display(self) -> Optional[str]:
        if not self.source_language_label:
            return None
        if self.target_language_label:
            return f"{self.source_language_label}→{self.target_language_label}"
        return self.source_language_label

    def _normalize_display_unit(self) -> str:
        """去除单位中与币种名称重复的前缀，如 '元/条' -> '条'"""
        _CURRENCY_PREFIXES = ("元/", "美元/", "港币/", "欧元/", "英镑/", "日元/")
        unit = self.unit
        for prefix in _CURRENCY_PREFIXES:
            if unit.startswith(prefix):
                return unit[len(prefix):]
        return unit

    @property
    def amount_display(self) -> str:
        from annotation_schemas import currency_symbol

        amount_text = format(self.amount.normalize(), "f")
        display_unit = self._normalize_display_unit()
        return f"{currency_symbol(self.currency)}{amount_text}/{display_unit}"

    @property
    def display(self) -> str:
        from annotation_schemas import ANNOTATION_PROJECT_TYPE_LABELS

        scope = [
            ANNOTATION_PROJECT_TYPE_LABELS.get(self.project_type, self.project_type),
            self.language_display,
        ]
        scope_text = "/".join(value for value in scope if value)
        return f"{scope_text}：{self.amount_display}" if scope_text else self.amount_display
