from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import workflow_models  # noqa: F401
from annotation_models import AnnotationProject
from annotation_schemas import AnnotationProjectCreate
from annotation_service import (
    build_annotation_project_name,
    ensure_annotation_project_for_consultation,
    generate_annotation_order_no,
)
from interpretation_models import InterpretationProject
from models import TranslationProject


class OrderQuery:
    def __init__(self, value):
        self.value = value

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def scalar(self):
        return self.value


class OrderDb:
    def __init__(self, value=None):
        self.value = value

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    def query(self, *_args):
        return OrderQuery(self.value)


def test_annotation_order_number_uses_required_format_and_increments():
    now = datetime(2026, 8, 1, 9)
    assert generate_annotation_order_no(OrderDb(), now) == "AP-20260801-001"
    assert generate_annotation_order_no(OrderDb("AP-20260801-009"), now) == "AP-20260801-010"


def test_annotation_project_name_lists_first_three_directions():
    assert build_annotation_project_name(
        "测试客户",
        ["audio_annotation", "quality_inspection"],
        ["英文", "粤语→普通话", "日文→中文", "法文→中文"],
    ) == "测试客户-英文、粤语→普通话、日文→中文等方向-音频标注、质检"


def test_payload_rejects_duplicate_language_and_invalid_price_scope():
    language_id = uuid4()
    with pytest.raises(ValueError, match="不能重复"):
        AnnotationProjectCreate(language_items=[
            {"source_language_id": language_id},
            {"source_language_id": language_id},
        ])

    with pytest.raises(ValueError, match="未选择的项目类型"):
        AnnotationProjectCreate(
            project_types=["audio_annotation"],
            price_items=[{
                "project_type": "quality_inspection",
                "amount": "0.15",
                "currency": "CNY",
                "unit": "条",
            }],
        )


def test_payload_rejects_submitted_time_before_dispatch():
    with pytest.raises(ValueError, match="提交时间不能早于"):
        AnnotationProjectCreate(
            task_dispatched_at=datetime(2026, 8, 11, 10),
            task_submitted_at=datetime(2026, 8, 11, 9),
        )


class EnsureQuery:
    def __init__(self, db, target):
        self.db = db
        self.target = target

    def filter(self, *_args):
        return self

    def first(self):
        if self.target is AnnotationProject:
            return self.db.annotation_project
        if self.target is InterpretationProject.id:
            return self.db.interpretation_project
        if self.target is TranslationProject:
            return self.db.translation_project
        return None


class EnsureDb:
    def __init__(self):
        self.annotation_project = None
        self.interpretation_project = None
        self.translation_project = None
        self.added = []

    def query(self, target):
        return EnsureQuery(self, target)

    def add(self, value):
        self.added.append(value)
        if isinstance(value, AnnotationProject):
            self.annotation_project = value

    def flush(self):
        pass


def test_confirmed_annotation_consultation_creation_is_idempotent(monkeypatch):
    db = EnsureDb()
    consultation = SimpleNamespace(
        id=uuid4(), client_id=uuid4(), consultation_time=datetime(2026, 8, 11, 9)
    )
    monkeypatch.setattr(
        "annotation_service.generate_annotation_order_no",
        lambda _db: "AP-20260811-001",
    )

    project, created = ensure_annotation_project_for_consultation(
        db, consultation, uuid4()
    )
    same_project, created_again = ensure_annotation_project_for_consultation(
        db, consultation, uuid4()
    )

    assert created is True
    assert created_again is False
    assert project is same_project
    assert project.project_status == "pending_confirmation"
    assert len(db.added) == 1
