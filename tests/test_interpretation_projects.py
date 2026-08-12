from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import workflow_models  # noqa: F401  注册 TranslationProject 使用的关系模型
from interpretation_models import InterpretationProject
from interpretation_schemas import (
    InterpretationLanguageDirectionInput,
    InterpretationNamePreviewRequest,
    InterpretationProjectCreate,
    InterpretationTimeRangeInput,
)
from interpretation_service import (
    build_interpretation_project_name,
    ensure_interpretation_project_for_consultation,
    format_interpretation_date_ranges,
    generate_interpretation_order_no,
)
from models import TranslationProject
from schemas import TranslatorCreate


def time_range(start, end):
    return InterpretationTimeRangeInput(scheduled_start=start, scheduled_end=end)


def test_name_uses_same_day_period_all_locations_directions_and_types():
    payload = InterpretationNamePreviewRequest(
        time_ranges=[time_range(datetime(2026, 8, 2, 8), datetime(2026, 8, 2, 11, 30))],
        locations=["东莞", "深圳"],
        language_directions=[
            InterpretationLanguageDirectionInput(
                source_language_id=uuid4(), target_language_id=uuid4()
            )
        ],
        project_types=["escort", "consecutive"],
    )

    assert build_interpretation_project_name(payload, ["朝鲜语 ↔ 中文（简体）"]) == (
        "2026年8月2日上午东莞、深圳朝鲜语 ↔ 中文（简体）"
        "陪同口译；会议交传口译项目"
    )


def test_date_ranges_compress_same_month_and_repeated_year():
    ranges = [
        time_range(datetime(2026, 8, 10, 9), datetime(2026, 8, 20, 18)),
        time_range(datetime(2026, 9, 10, 9), datetime(2026, 9, 30, 18)),
        time_range(datetime(2027, 1, 2, 18), datetime(2027, 1, 2, 22)),
    ]

    assert format_interpretation_date_ranges(ranges) == (
        "2026年8月10-20日；9月10-30日；2027年1月2日晚上"
    )


@pytest.mark.parametrize(
    ("start", "end", "label"),
    [
        (datetime(2026, 1, 1, 8), datetime(2026, 1, 1, 12), "上午"),
        (datetime(2026, 1, 1, 13), datetime(2026, 1, 1, 18), "下午"),
        (datetime(2026, 1, 1, 18), datetime(2026, 1, 1, 23, 59), "晚上"),
        (datetime(2026, 1, 1, 12, 30), datetime(2026, 1, 1, 13, 30), ""),
    ],
)
def test_same_day_period_boundaries(start, end, label):
    assert format_interpretation_date_ranges([time_range(start, end)]) == f"2026年1月1日{label}"


def test_name_rejects_missing_required_segments():
    payload = InterpretationNamePreviewRequest()
    with pytest.raises(ValueError, match="预定时间.*项目地点.*口译方向.*项目类型"):
        build_interpretation_project_name(payload, [])


def test_nested_payload_rejects_duplicate_bidirectional_pair_and_translator():
    first, second, translator_id = uuid4(), uuid4(), uuid4()
    with pytest.raises(ValueError, match="双向口译方向不能重复"):
        InterpretationProjectCreate(
            language_directions=[
                {"source_language_id": first, "target_language_id": second},
                {"source_language_id": second, "target_language_id": first},
            ]
        )
    with pytest.raises(ValueError, match="同一译员不能重复安排"):
        InterpretationProjectCreate(
            interpreter_assignments=[
                {"translator_id": translator_id},
                {"translator_id": translator_id},
            ]
        )


def test_interpreter_requirements_and_translator_level_validation():
    payload = InterpretationProjectCreate(
        required_interpreter_count=2,
        required_interpreter_gender="女",
        required_interpretation_level="高级",
        interpreter_special_requirements="有展会经验",
        interpreter_height_requirement="165cm以上",
        interpreter_appearance_requirement="形象专业",
        interpreter_dress_requirement="商务正装",
    )
    assert payload.required_interpreter_count == 2
    assert payload.required_interpretation_level == "高级"
    assert TranslatorCreate(translator_name="测试译员", interpretation_level="中级").interpretation_level == "中级"

    with pytest.raises(ValueError, match="口译水平要求"):
        InterpretationProjectCreate(required_interpretation_level="专家级")
    with pytest.raises(ValueError):
        TranslatorCreate(translator_name="测试译员", interpretation_level="专家级")


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


def test_interpretation_order_number_uses_eight_digit_date_and_increments():
    now = datetime(2026, 8, 11, 10)
    assert generate_interpretation_order_no(OrderDb(), now) == "IP-20260811-001"
    assert generate_interpretation_order_no(OrderDb("IP-20260811-009"), now) == "IP-20260811-010"


class EnsureQuery:
    def __init__(self, db, target):
        self.db = db
        self.target = target

    def filter(self, *_args):
        return self

    def first(self):
        if self.target is InterpretationProject:
            return self.db.interpretation_project
        return self.db.translation_project


class EnsureDb:
    def __init__(self):
        self.interpretation_project = None
        self.translation_project = None
        self.added = []

    def query(self, target):
        if target is TranslationProject.id:
            return EnsureQuery(self, TranslationProject)
        return EnsureQuery(self, target)

    def add(self, value):
        self.added.append(value)
        if isinstance(value, InterpretationProject):
            self.interpretation_project = value

    def flush(self):
        pass


def test_confirmed_consultation_creation_is_idempotent(monkeypatch):
    db = EnsureDb()
    consultation = SimpleNamespace(
        id=uuid4(), client_id=uuid4(), consultation_time=datetime(2026, 8, 11, 9)
    )
    monkeypatch.setattr(
        "interpretation_service.generate_interpretation_order_no",
        lambda _db: "IP-20260811-001",
    )

    project, created = ensure_interpretation_project_for_consultation(db, consultation, uuid4())
    same_project, created_again = ensure_interpretation_project_for_consultation(db, consultation, uuid4())

    assert created is True
    assert created_again is False
    assert project is same_project
    assert project.project_status == "initial_follow_up"
    assert len(db.added) == 1
