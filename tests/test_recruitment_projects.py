from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from annotation_models import AnnotationProject
from interpretation_models import InterpretationProject
from models import AppUser, Client, SubClient, TranslationProject
from recruitment_models import (
    RecruitmentCandidate,
    RecruitmentCandidateCommunication,
    RecruitmentCandidateInterview,
    RecruitmentProject,
    RecruitmentProjectProgress,
    RecruitmentResumeSource,
)
from recruitment_schemas import (
    RecruitmentCandidateCreate,
    RecruitmentCandidateCommunicationCreate,
    RecruitmentCandidatePatch,
    RecruitmentNamePreviewRequest,
    RecruitmentProjectCreate,
    RecruitmentProjectStatusUpdate,
    RecruitmentResumeSourceCreate,
)
from recruitment_service import (
    _resolve_client as resolve_recruitment_client,
    _sync_candidate_interviews,
    build_recruitment_project_name,
    create_candidate_communication,
    create_or_get_resume_source,
    ensure_recruitment_project_for_consultation,
    generate_recruitment_order_no,
    patch_candidate,
    update_recruitment_project_status,
)
from annotation_service import _resolve_client as resolve_annotation_client
from crud import _resolve_or_create_project_client
from interpretation_service import _resolve_client as resolve_interpretation_client


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
    assert generate_recruitment_order_no(OrderDb(), now) == "HP-260801-001"
    assert generate_recruitment_order_no(OrderDb("HP-260801-009"), now) == "HP-260801-010"


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


def test_recruitment_payload_accepts_manual_client_fields():
    payload = RecruitmentProjectCreate(
        client_short_name="  新客户  ",
        client_name="  新客户有限公司  ",
        client_code="  TEMP-001  ",
    )

    assert payload.client_short_name == "新客户"
    assert payload.client_name == "新客户有限公司"
    assert payload.client_code == "TEMP-001"


class MissingClientQuery:
    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def first(self):
        return None


class MissingClientDb:
    def __init__(self):
        self.added = None

    def query(self, target):
        assert target in {Client, SubClient}
        return MissingClientQuery()

    def add(self, value):
        self.added = value

    def flush(self):
        self.added.id = uuid4()


def test_translation_client_resolver_creates_pending_client_for_new_short_name(monkeypatch):
    db = MissingClientDb()
    monkeypatch.setattr("crud.generate_client_code", lambda _db: "C000001")

    client_id, sub_client_id, created = _resolve_or_create_project_client(
        db, "  新增简称  ", client_name="  新增客户全称  "
    )

    assert created is True
    assert client_id == db.added.id
    assert sub_client_id is None
    assert db.added.client_short_name == "新增简称"
    assert db.added.client_name == "新增客户全称"
    assert db.added.client_code == "C000001"
    assert db.added.client_status == "pending"


@pytest.mark.parametrize(
    "resolver",
    [resolve_interpretation_client, resolve_annotation_client, resolve_recruitment_client],
)
def test_three_project_resolvers_reuse_translation_client_logic(monkeypatch, resolver):
    parent_id, sub_client_id = uuid4(), uuid4()
    monkeypatch.setattr(
        "crud._resolve_or_create_project_client",
        lambda *_args: (parent_id, sub_client_id, False),
    )
    data = {
        "client_id": None,
        "sub_client_id": None,
        "client_short_name": "已有子客户",
        "client_name": None,
        "client_code": None,
    }

    resolver(SimpleNamespace(), data)

    assert data["client_id"] == parent_id
    assert data["sub_client_id"] == sub_client_id


def test_project_status_patch_validates_supported_status():
    assert RecruitmentProjectStatusUpdate(project_status="interviewing").project_status == "interviewing"
    with pytest.raises(ValueError, match="不支持"):
        RecruitmentProjectStatusUpdate(project_status="unknown")


class StatusUpdateDb:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True


def test_inline_project_status_update_records_progress(monkeypatch):
    project = RecruitmentProject(id=uuid4(), order_no="HP-260817-099", project_status="sourcing")
    db = StatusUpdateDb()
    monkeypatch.setattr("recruitment_service.get_recruitment_project", lambda *_args: project)

    updated = update_recruitment_project_status(
        db, project.id, "interviewing", operator_id=uuid4()
    )

    assert updated.project_status == "interviewing"
    assert db.committed is True
    progress = next(item for item in db.added if isinstance(item, RecruitmentProjectProgress))
    assert progress.from_status == "sourcing"
    assert progress.to_status == "interviewing"
    assert progress.note == "项目状态变更"


def test_candidate_tracking_payloads_normalize_and_validate():
    patch = RecruitmentCandidatePatch(first_interview_details="  沟通顺畅  ")
    assert patch.model_dump(exclude_unset=True) == {"first_interview_details": "沟通顺畅"}
    assert RecruitmentResumeSourceCreate(label="  猎聘  ").label == "猎聘"
    with pytest.raises(ValueError):
        RecruitmentCandidateCommunicationCreate(communication_date=date(2026, 8, 12), details="   ")


def test_candidate_interviews_support_continuous_dynamic_rounds():
    payload = RecruitmentCandidateCreate(
        candidate_name="动态面试人选",
        interviews=[
            {"round_no": 1, "interview_date": date(2026, 8, 18), "details": " 一面通过 "},
            {"round_no": 2, "details": "二面待安排"},
            {"round_no": 3},
        ],
    )
    assert [item.round_no for item in payload.interviews] == [1, 2, 3]
    assert payload.interviews[0].details == "一面通过"
    with pytest.raises(ValueError, match="连续排列"):
        RecruitmentCandidateCreate(
            candidate_name="跳号人选",
            interviews=[{"round_no": 1}, {"round_no": 3}],
        )


class InterviewSyncDb:
    def __init__(self):
        self.added = []
        self.deleted = []

    def add(self, value):
        self.added.append(value)

    def delete(self, value):
        self.deleted.append(value)


def test_candidate_interview_sync_creates_rounds_and_updates_legacy_fields():
    db = InterviewSyncDb()
    candidate = RecruitmentCandidate(
        id=uuid4(), project_id=uuid4(), candidate_name="同步面试人选"
    )
    _sync_candidate_interviews(db, candidate, [
        {"round_no": 1, "interview_date": date(2026, 8, 18), "details": "一面通过"},
        {"round_no": 2, "interview_date": date(2026, 8, 20), "details": "二面通过"},
        {"round_no": 3, "interview_date": None, "details": "待安排"},
    ])

    assert len([item for item in db.added if isinstance(item, RecruitmentCandidateInterview)]) == 3
    assert candidate.first_interview_date == date(2026, 8, 18)
    assert candidate.second_interview_details == "二面通过"


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
        lambda _db: "HP-260811-001",
    )

    project, created = ensure_recruitment_project_for_consultation(db, consultation, uuid4())
    same_project, created_again = ensure_recruitment_project_for_consultation(db, consultation, uuid4())

    assert created is True
    assert created_again is False
    assert project is same_project
    assert project.project_status == "pending_setup"
    assert len([item for item in db.added if isinstance(item, RecruitmentProject)]) == 1
    assert len([item for item in db.added if isinstance(item, RecruitmentProjectProgress)]) == 1
