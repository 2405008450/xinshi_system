from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from language_catalog import normalize_language_search_text
from resource_models import ResourcePerson
from resource_schemas import ResourcePersonCreate


def base_payload(**overrides):
    values = {
        "full_name": "张三",
        "chinese_name": "张三",
        "capabilities": [],
    }
    values.update(overrides)
    return ResourcePersonCreate(**values)


def test_talent_profile_accepts_structured_names_education_languages_and_certificates():
    language_id = uuid4()
    payload = base_payload(
        english_name="San Zhang",
        nickname="小张",
        other_names=["Zhang San"],
        birth_year_month="2000-09",
        employment_status="student",
        enrollment_year=2023,
        program_duration_years=4,
        highest_education="bachelor",
        education_experiences=[{
            "education_level": "bachelor",
            "institution": "测试大学",
            "major": "英语",
            "graduation_year": 2027,
        }],
        language_skills=[{
            "language_id": language_id,
            "role": "native",
            "priority": 1,
            "proficiency": "very_familiar",
        }],
        certificates=[{
            "certificate_type": "language",
            "name": "测试证书",
            "language_id": language_id,
            "material_received": True,
        }],
    )
    assert payload.birth_year_month == "2000-09"
    assert payload.language_skills[0].proficiency == "very_familiar"
    assert payload.certificates[0].material_received is True


def test_student_with_enrollment_year_requires_program_duration():
    with pytest.raises(ValueError, match="学制"):
        base_payload(
            employment_status="student",
            enrollment_year=2023,
        )


def test_duplicate_language_role_is_rejected():
    language_id = uuid4()
    item = {"language_id": language_id, "role": "foreign", "priority": 1}
    with pytest.raises(ValueError, match="语言能力不能重复"):
        base_payload(language_skills=[item, item])


def test_current_age_prefers_birth_year_month():
    today = date.today()
    month = 1 if today.month == 12 else today.month + 1
    person = SimpleNamespace(
        birth_year_month=f"{today.year - 20:04d}-{month:02d}",
        birth_date=None,
    )
    assert ResourcePerson.current_age.fget(person) == 19


def test_language_search_normalization_handles_case_width_and_separators():
    assert normalize_language_search_text(" EN-us ") == "enus"
    assert normalize_language_search_text("English (United States)") == "englishunitedstates"
