from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from annotation_models import AnnotationProject
from interpretation_models import InterpretationProject
from models import AppUser, Client, TranslationProject
from recruitment_models import (
    RecruitmentCandidate,
    RecruitmentCandidateCommunication,
    RecruitmentProject,
    RecruitmentProjectProgress,
    RecruitmentResumeSource,
)
from recruitment_schemas import (
    RecruitmentCandidateCommunicationCreate,
    RecruitmentCandidatePatch,
    RecruitmentNamePreviewRequest,
    RecruitmentProjectCreate,
    RecruitmentResumeSourceCreate,
)
from recruitment_service import (
    build_recruitment_project_name,
    create_candidate_communication,
    create_or_get_resume_source,
    ensure_recruitment_project_for_consultation,
    generate_recruitment_order_no,
    patch_candidate,
)


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


def test_recruitment_order_number_uses_hp_format_and_increments():
    now = datetime(2026, 8, 1, 9)
    assert generate_recruitment_order_no(OrderDb(), now) == "HP-20260801-001"
    assert generate_recruitment_order_no(OrderDb("HP-20260801-009"), now) == "HP-20260801-010"


def test_project_name_lists_three_directions_then_suffix():
    payload = RecruitmentNamePreviewRequest(
        employment_start=date(2026, 8, 1),
        employment_end=date(2026, 12, 31),
        work_location="深圳",
        position_title="海外销售",
        language_directions=[
            {"source_language_id": uuid4()},
            {"source_language_id": uuid4()},
            {"source_language_id": uuid4()},
            {"source_language_id": uuid4()},
        ],
    )
    assert build_recruitment_project_name(payload, ["英文", "日文", "粤语翻译成普通话", "法文"]) == (
        "2026年08月01日—2026年12月31日深圳英文、日文、粤语翻译成普通话等方向海外销售"
    )


def test_payload_normalizes_headcount_and_anytime_date_rules():
    payload = RecruitmentProjectCreate(
        headcount_min=4,
        headcount_max=5,
        target_onboard_type="anytime",
        target_onboard_date=date(2026, 9, 1),
    )
    assert payload.target_onboard_date is None
    with pytest.raises(ValueError, match="上限不能小于下限"):
        RecruitmentProjectCreate(headcount_min=5, headcount_max=4)


def test_candidate_tracking_payloads_normalize_and_validate():
    patch = RecruitmentCandidatePatch(first_interview_details="  沟通顺畅  ")
    assert patch.model_dump(exclude_unset=True) == {"first_interview_details": "沟通顺畅"}
    assert RecruitmentResumeSourceCreate(label="  猎聘  ").label == "猎聘"
    with pytest.raises(ValueError):
        RecruitmentCandidateCommunicationCreate(communication_date=date(2026, 8, 12), details="   ")


class CommunicationQuery:
    def __init__(self, db, target):
        self.db = db
        self.target = target

    def filter(self, *_args):
        return self

    def first(self):
        if self.target is RecruitmentCandidate.id:
            return (self.db.candidate_id,)
        return None

    def scalar(self):
        return self.db.last_sequence


class CommunicationDb:
    def __init__(self):
        self.candidate_id = uuid4()
        self.last_sequence = 3
        self.added = None

    def query(self, target):
        return CommunicationQuery(self, target)

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    def add(self, value):
        self.added = value

    def commit(self):
        pass

    def refresh(self, value):
        value.id = uuid4()
        value.created_at = datetime(2026, 8, 12, 10)
        value.updated_at = datetime(2026, 8, 12, 10)


def test_candidate_communication_appends_next_sequence():
    db = CommunicationDb()
    payload = RecruitmentCandidateCommunicationCreate(
        communication_date=date(2026, 8, 12), details="第二轮意向确认"
    )
    record = create_candidate_communication(db, db.candidate_id, payload)
    assert isinstance(record, RecruitmentCandidateCommunication)
    assert record.sequence_no == 4
    assert record.communication_date == date(2026, 8, 12)
    assert record.details == "第二轮意向确认"


class ExistingSourceQuery:
    def __init__(self, existing):
        self.existing = existing

    def filter(self, *_args):
        return self

    def first(self):
        return self.existing


class ExistingSourceDb:
    def __init__(self, existing):
        self.existing = existing

    def query(self, _target):
        return ExistingSourceQuery(self.existing)


def test_resume_source_creation_reuses_case_insensitive_existing_value():
    existing = SimpleNamespace(id=uuid4(), label="BOSS", is_custom=False)
    result = create_or_get_resume_source(ExistingSourceDb(existing), "  boss  ", uuid4())
    assert result is existing


class PatchQuery:
    def __init__(self, db, target):
        self.db = db
        self.target = target

    def options(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def first(self):
        if self.target is RecruitmentCandidate:
            return self.db.candidate
        return None


class PatchDb:
    def __init__(self):
        self.candidate = SimpleNamespace(
            id=uuid4(), candidate_name="历史人选", first_interview_date=None,
            first_interview_details=None, updated_at=None,
        )

    def query(self, target):
        return PatchQuery(self, target)

    def commit(self):
        pass


def test_candidate_patch_only_updates_submitted_tracking_fields():
    db = PatchDb()
    updated = patch_candidate(db, db.candidate.id, RecruitmentCandidatePatch(
        first_interview_date=date(2026, 8, 15), first_interview_details="已通过"
    ))
    assert updated.candidate_name == "历史人选"
    assert updated.first_interview_date == date(2026, 8, 15)
    assert updated.first_interview_details == "已通过"


class EnsureQuery:
    def __init__(self, db, target):
        self.db = db
        self.target = target

    def filter(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def first(self):
        if self.target is RecruitmentProject:
            return self.db.recruitment_project
        return None

    def all(self):
        return []


class EnsureDb:
    def __init__(self):
        self.recruitment_project = None
        self.added = []

    def query(self, target):
        return EnsureQuery(self, target)

    def add(self, value):
        self.added.append(value)
        if isinstance(value, RecruitmentProject):
            self.recruitment_project = value

    def flush(self):
        pass


def test_confirmed_recruitment_consultation_creation_is_idempotent(monkeypatch):
    db = EnsureDb()
    consultation = SimpleNamespace(
        id=uuid4(), client_id=None, consultation_time=datetime(2026, 8, 11, 9)
    )
    monkeypatch.setattr(
        "recruitment_service.generate_recruitment_order_no",
        lambda _db: "HP-20260811-001",
    )

    project, created = ensure_recruitment_project_for_consultation(db, consultation, uuid4())
    same_project, created_again = ensure_recruitment_project_for_consultation(db, consultation, uuid4())

    assert created is True
    assert created_again is False
    assert project is same_project
    assert project.project_status == "pending_setup"
    assert len([item for item in db.added if isinstance(item, RecruitmentProject)]) == 1
    assert len([item for item in db.added if isinstance(item, RecruitmentProjectProgress)]) == 1
