from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

import workflow_models  # noqa: F401
from annotation_models import AnnotationProject, AnnotationProjectPriceItem
from annotation_schemas import AnnotationProjectCreate, AnnotationProjectListResponse
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
    assert generate_annotation_order_no(OrderDb(), now) == "AP-260801-001"
    assert generate_annotation_order_no(OrderDb("AP-260801-009"), now) == "AP-260801-010"


def test_annotation_project_name_lists_first_three_directions():
    assert build_annotation_project_name(
        "测试客户",
        ["audio_annotation", "quality_inspection"],
        ["英文", "粤语→普通话", "日文→中文", "法文→中文"],
        date(2026, 8, 13),
    ) == "【测试客户-20260813-英文、粤语→普通话、日文→中文等方向-音频标注、质检】"


def test_annotation_project_name_stays_empty_without_business_fields():
    assert build_annotation_project_name("", [], [], date(2026, 8, 13)) == ""


def test_annotation_project_list_response_keeps_language_items():
    language_id = uuid4()
    response = AnnotationProjectListResponse.model_validate(
        SimpleNamespace(
            id=uuid4(),
            order_no="AP-260826-001",
            project_status="initial_consultation",
            status_effective_on=date(2026, 8, 26),
            language_items=[
                SimpleNamespace(
                    id=uuid4(),
                    source_language_id=language_id,
                    target_language_id=None,
                    sequence_no=1,
                    source_language_label="温州话",
                    target_language_label=None,
                    display="温州话",
                )
            ],
            created_at=datetime(2026, 8, 26, 9),
            updated_at=datetime(2026, 8, 26, 9),
        )
    )

    assert response.language_items[0].source_language_id == language_id
    assert response.language_items[0].display == "温州话"


def test_customer_price_summary_shows_amount_only():
    project = AnnotationProject()
    project.price_items = [
        AnnotationProjectPriceItem(
            amount=Decimal("123123"),
            currency="CNY",
            unit="条",
            project_type="audio_annotation",
        ),
        AnnotationProjectPriceItem(
            amount=Decimal("0.15"),
            currency="USD",
            unit="小时",
            project_type="quality_inspection",
        ),
    ]

    assert project.customer_price_summary == "￥123123/条；$0.15/小时"
    assert project.price_items[0].amount_display == "￥123123/条"
    assert project.price_items[1].amount_display == "$0.15/小时"
    assert AnnotationProjectPriceItem(amount=Decimal("8"), unit="条").amount_display == "￥8/条"


def test_price_item_currency_is_optional():
    payload = AnnotationProjectCreate(
        project_types=["audio_annotation"],
        price_items=[{
            "project_type": "audio_annotation",
            "amount": "0.15",
            "unit": "条",
        }],
    )
    assert payload.price_items[0].currency is None

    payload = AnnotationProjectCreate(
        project_types=["audio_annotation"],
        price_items=[{
            "project_type": "audio_annotation",
            "amount": "0.15",
            "currency": "cny",
            "unit": "条",
        }],
    )
    assert payload.price_items[0].currency == "CNY"

    payload = AnnotationProjectCreate(
        project_types=["audio_annotation"],
        price_items=[{
            "project_type": "audio_annotation",
            "amount": "0.15",
            "currency": "usd",
            "unit": "条",
        }],
    )
    assert payload.price_items[0].currency == "USD"

    with pytest.raises(ValueError, match="三位代码"):
        AnnotationProjectCreate(
            project_types=["audio_annotation"],
            price_items=[{
                "project_type": "audio_annotation",
                "amount": "0.15",
                "currency": "US",
                "unit": "条",
            }],
        )


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


def test_payload_normalizes_annotation_project_paths(monkeypatch):
    monkeypatch.setenv("OPENPATH_ALLOWED_ROOTS", r"\\server\annotation")
    payload = AnnotationProjectCreate(
        project_path=r"  \\server\annotation  ",
        quotation_path="  D:/报价单  ",
        contract_path="   ",
    )

    assert payload.project_path == r"\\server\annotation"
    assert payload.quotation_path == "D:/报价单"
    assert payload.contract_path is None


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
        lambda _db: "AP-260811-001",
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
    assert project.project_status == "initial_consultation"
    assert len(db.added) == 1
