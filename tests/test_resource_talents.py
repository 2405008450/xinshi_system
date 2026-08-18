from uuid import uuid4
from types import SimpleNamespace

import pytest

from annotation_schemas import AnnotationProjectCreate
from recruitment_schemas import RecruitmentCandidateCreate
from resource_schemas import ResourcePersonCreate
from resource_models import ResourcePerson
from resource_service import extract_contact_identifiers, normalize_email, normalize_phone


def test_person_can_enable_multiple_capabilities_with_typed_profiles():
    payload = ResourcePersonCreate(
        full_name="多能力人员",
        capabilities=[
            {"capability_type": "written_translation"},
            {"capability_type": "interpretation"},
            {"capability_type": "annotation"},
        ],
        interpretation_profile={
            "interpretation_level": "高级",
            "interpretation_modes": ["simultaneous", "consecutive"],
        },
        annotation_profile={"task_types": ["文本标注"]},
    )

    assert {item.capability_type for item in payload.capabilities} == {
        "written_translation", "interpretation", "annotation"
    }
    assert payload.interpretation_profile.interpretation_modes == [
        "simultaneous", "consecutive"
    ]


def test_profile_requires_matching_capability_and_capability_cannot_repeat():
    with pytest.raises(ValueError, match="专业档案必须启用对应能力"):
        ResourcePersonCreate(
            full_name="无能力档案",
            interpretation_profile={"interpretation_modes": ["simultaneous"]},
        )
    with pytest.raises(ValueError, match="同一种能力不能重复添加"):
        ResourcePersonCreate(
            full_name="重复能力",
            capabilities=[
                {"capability_type": "annotation"},
                {"capability_type": "annotation"},
            ],
        )


def test_simultaneous_and_consecutive_are_interpretation_modes_not_capabilities():
    with pytest.raises(ValueError):
        ResourcePersonCreate(
            full_name="错误能力",
            capabilities=[{"capability_type": "simultaneous"}],
        )


def test_contact_identifiers_are_normalized_for_duplicate_detection():
    phone, email = extract_contact_identifiers("电话：+86 138-0013-8000；Mail: Test@Example.COM")

    assert phone == "8613800138000"
    assert email == "test@example.com"
    assert normalize_phone("138 0013 8000") == "13800138000"
    assert normalize_email(" Test@Example.COM ") == "test@example.com"


def test_recruitment_candidate_can_reuse_one_person_in_multiple_projects():
    person_id = uuid4()
    first = RecruitmentCandidateCreate(person_id=person_id, candidate_name="候选人")
    second = RecruitmentCandidateCreate(person_id=person_id, candidate_name="候选人")

    assert first.person_id == second.person_id == person_id


def test_annotation_project_rejects_duplicate_person_assignments():
    person_id = uuid4()
    with pytest.raises(ValueError, match="同一标注人员不能重复安排"):
        AnnotationProjectCreate(assignees=[
            {"person_id": person_id},
            {"person_id": person_id},
        ])


def test_talent_list_summary_combines_professional_profile_fields():
    person = SimpleNamespace(
        written_profile=SimpleNamespace(languages="中英"),
        interpretation_profile=SimpleNamespace(languages="中英"),
        career_profile=SimpleNamespace(
        industries=["汽车", "制造"],
        job_titles=["译员"],
        years_experience=5,
        ),
    )

    assert ResourcePerson.language_directions.fget(person) == ["中英"]
    assert ResourcePerson.industries.fget(person) == ["汽车", "制造"]
    assert ResourcePerson.job_titles.fget(person) == ["译员"]
    assert ResourcePerson.years_experience.fget(person) == 5
