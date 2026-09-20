from datetime import date
from uuid import uuid4
from types import SimpleNamespace

import pytest

from annotation_schemas import AnnotationProjectCreate
from recruitment_schemas import RecruitmentCandidateCreate
from resource_schemas import ResourcePersonCreate, ResourcePersonListResponse, ResourcePersonNameUpdate, ResourcePersonStatusUpdate, ResourcePersonUpdate, TalentOptionResponse
from resource_models import ResourcePerson
from resource_service import _sync_annotation_language_skills, _talent_ordering, extract_contact_identifiers, normalize_email, normalize_phone, update_recruitment_talent
from routers.talents import _field_filters
from routers.talent_options import ASSIGNABLE_TALENT_STATUSES, read_talent_options


def test_person_can_enable_multiple_capabilities_with_typed_profiles():
    annotation_language_id = uuid4()
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
        annotation_language_skills=[{"source_language_id": annotation_language_id}],
    )

    assert {item.capability_type for item in payload.capabilities} == {
        "written_translation", "interpretation", "annotation"
    }
    assert payload.interpretation_profile.interpretation_modes == [
        "simultaneous", "consecutive"
    ]


def test_person_locale_profile_fields_are_typed_and_default_to_lists():
    payload = ResourcePersonCreate(
        full_name="方言标注员",
        gender="女",
        birth_date="1998-06-15",
        native_place="福建泉州",
        residence_address="福建厦门",
        dialects=["闽南语"],
        dialect_regions=["泉州石狮"],
    )

    assert payload.birth_date.isoformat() == "1998-06-15"
    assert payload.dialects == ["闽南语"]
    assert payload.dialect_regions == ["泉州石狮"]
    assert ResourcePersonListResponse.model_fields["dialects"].default_factory() == []


def test_talent_performance_fields_accept_structured_values_and_preserve_legacy_evaluation():
    payload = ResourcePersonCreate(
        full_name="综合表现人才",
        overall_score=9,
        overall_rating="原综合评价作为具体评价保留",
        cooperation_level="high",
        cooperation_note="沟通顺畅",
        punctuality_level="medium",
        audio_annotation_score=8,
        non_audio_annotation_score=7,
        collection_score=10,
    )

    assert payload.overall_score == 9
    assert payload.overall_rating == "原综合评价作为具体评价保留"
    assert payload.cooperation_level == "high"
    assert payload.collection_score == 10


@pytest.mark.parametrize("field", [
    "overall_score", "audio_annotation_score",
    "non_audio_annotation_score", "collection_score",
])
@pytest.mark.parametrize("value", [0, 11, 8.5])
def test_talent_performance_scores_require_integers_from_one_to_ten(field, value):
    with pytest.raises(ValueError):
        ResourcePersonCreate(full_name="评分越界", **{field: value})


def test_talent_performance_levels_reject_unknown_values():
    with pytest.raises(ValueError):
        ResourcePersonCreate(full_name="等级错误", cooperation_level="very_high")


def test_talent_performance_filters_are_numeric_ranges():
    filters = _field_filters(
        '{"overall_score":{"op":"between","min":7,"max":10},'
        '"audio_annotation_score":{"op":"between","min":6,"max":9}}'
    )

    assert filters["overall_score"]["min"] == 7
    assert filters["audio_annotation_score"]["max"] == 9


def test_talent_performance_sort_keeps_nulls_last_and_stable_ties():
    ordering = _talent_ordering("overall_score_asc")

    assert "overall_score ASC NULLS LAST" in str(ordering[0])
    assert "updated_at DESC" in str(ordering[1])
    assert "id DESC" in str(ordering[2])


def test_recruitment_update_cannot_overwrite_talent_performance(monkeypatch):
    person = SimpleNamespace(
        id=uuid4(), full_name="招聘人才", chinese_name="招聘人才", english_name=None,
        nickname=None, other_names=[], overall_score=9, overall_rating="保留评价",
        cooperation_level="high", cooperation_note="保留说明", punctuality_level="medium",
        punctuality_note="守时说明", audio_annotation_score=8,
        audio_annotation_evaluation="音频评价", non_audio_annotation_score=7,
        non_audio_annotation_evaluation="非音频评价", collection_score=10,
        collection_evaluation="采集评价", career_profile=None,
    )
    payload = ResourcePersonUpdate(
        full_name="招聘人才已编辑", overall_score=1, overall_rating="不应覆盖",
        cooperation_level="low", remarks="招聘端允许修改的备注",
    )
    db = SimpleNamespace(flush=lambda: None, commit=lambda: None)
    monkeypatch.setattr("resource_service.get_talent", lambda *_args: person)
    monkeypatch.setattr("resource_service.find_duplicate_talents", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("resource_service._sync_owned_collections", lambda *_args: None)
    monkeypatch.setattr("resource_service._sync_display_name", lambda *_args: None)
    monkeypatch.setattr("resource_service._sync_legacy_translator", lambda *_args: None)

    updated = update_recruitment_talent(db, person.id, payload)

    assert updated.overall_score == 9
    assert updated.overall_rating == "保留评价"
    assert updated.cooperation_level == "high"
    assert updated.remarks == "招聘端允许修改的备注"


def test_annotation_language_skill_supports_single_dialect_and_bilingual_direction():
    dialect_id, source_id, target_id = uuid4(), uuid4(), uuid4()
    payload = ResourcePersonCreate(
        full_name="方言标注员",
        capabilities=[{"capability_type": "annotation"}],
        annotation_language_skills=[
            {"source_language_id": dialect_id},
            {"source_language_id": source_id, "target_language_id": target_id},
        ],
    )

    assert payload.annotation_language_skills[0].target_language_id is None
    assert payload.annotation_language_skills[1].target_language_id == target_id


def test_annotation_language_skill_requires_annotation_capability_and_distinct_languages():
    language_id = uuid4()
    with pytest.raises(ValueError, match="必须启用标注能力"):
        ResourcePersonCreate(
            full_name="未启用标注能力",
            annotation_language_skills=[{"source_language_id": language_id}],
        )
    with pytest.raises(ValueError, match="不能相同"):
        ResourcePersonCreate(
            full_name="错误方向",
            capabilities=[{"capability_type": "annotation"}],
            annotation_language_skills=[{
                "source_language_id": language_id,
                "target_language_id": language_id,
            }],
        )


def test_annotation_language_skill_sync_reuses_unchanged_rows_and_applies_diff(monkeypatch):
    monkeypatch.setattr(
        "resource_service.ResourceAnnotationLanguageSkill",
        lambda **values: SimpleNamespace(**values),
    )
    kept_source, removed_source, added_source = uuid4(), uuid4(), uuid4()
    kept = SimpleNamespace(source_language_id=kept_source, target_language_id=None)
    removed = SimpleNamespace(source_language_id=removed_source, target_language_id=None)
    person = SimpleNamespace(annotation_language_skills=[kept, removed])
    payload = ResourcePersonCreate(
        full_name="差量更新标注员",
        capabilities=[{"capability_type": "annotation"}],
        annotation_language_skills=[
            {"source_language_id": kept_source},
            {"source_language_id": added_source},
        ],
    )

    class LanguageQuery:
        def filter(self, *_args):
            return self

        def all(self):
            return [(kept_source,), (added_source,)]

    db = SimpleNamespace(query=lambda *_args: LanguageQuery())

    _sync_annotation_language_skills(db, person, payload)

    assert person.annotation_language_skills[0] is kept
    assert removed not in person.annotation_language_skills
    assert {
        (item.source_language_id, item.target_language_id)
        for item in person.annotation_language_skills
    } == {(kept_source, None), (added_source, None)}


def test_new_annotator_requires_annotation_language_skill():
    with pytest.raises(ValueError, match="必须填写标注语言方向"):
        ResourcePersonCreate(
            full_name="缺少语种的标注员",
            capabilities=[{"capability_type": "annotation"}],
        )


def test_blank_optional_fields_coerce_to_none_instead_of_422():
    payload = ResourcePersonCreate(
        full_name="口译未定级",
        birth_date="",
        capabilities=[{"capability_type": "interpretation"}],
        interpretation_profile={"interpretation_level": "", "interpretation_modes": []},
    )

    assert payload.birth_date is None
    assert payload.interpretation_profile.interpretation_level is None


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
    with pytest.raises(ValueError, match="同一人员、语种与角色不能重复安排"):
        AnnotationProjectCreate(assignees=[
            {"person_id": person_id},
            {"person_id": person_id},
        ])


def test_talent_status_patch_accepts_supported_values_only():
    assert ResourcePersonStatusUpdate(status="active").status == "active"
    with pytest.raises(ValueError):
        ResourcePersonStatusUpdate(status="unknown")


def test_talent_name_patch_requires_a_non_blank_name():
    assert ResourcePersonNameUpdate(full_name="  修正姓名  ").full_name == "修正姓名"
    with pytest.raises(ValueError):
        ResourcePersonNameUpdate(full_name="   ")


def test_project_talent_options_include_active_and_standby_people():
    assert ASSIGNABLE_TALENT_STATUSES == ("active", "standby")


def test_project_talent_options_expose_gender_and_birth_date_for_derived_columns():
    option = TalentOptionResponse(
        id=uuid4(),
        full_name="测试人才",
        status="active",
        gender="女",
        birth_date="2000-09-01",
    )

    assert option.gender == "女"
    assert option.birth_date == date(2000, 9, 1)


def test_project_talent_options_apply_assignable_status_filter(monkeypatch):
    captured = {}

    def fake_get_talents(_db, **filters):
        captured.update(filters)
        return []

    monkeypatch.setattr("routers.talent_options.get_talents", fake_get_talents)
    monkeypatch.setattr("routers.talent_options.can_view_talent_contacts", lambda *_args: False)

    assert read_talent_options(
        "annotation",
        keyword=None,
        limit=500,
        db=object(),
        current_user=SimpleNamespace(id="user-id"),
    ) == []
    assert captured["statuses"] == ("active", "standby")
    assert captured["capability_status"] == "active"
    assert captured["include_contact_search"] is False


def test_inline_talent_status_update_skips_write_when_unchanged(monkeypatch):
    from resource_service import update_talent_status

    person = SimpleNamespace(id=uuid4(), status="standby")
    wrote = {"called": False}
    db = SimpleNamespace(flush=lambda: wrote.update(called=True), commit=lambda: wrote.update(called=True))
    monkeypatch.setattr("resource_service.get_talent", lambda *_args: person)
    monkeypatch.setattr("resource_service._sync_legacy_translator", lambda *_args: wrote.update(called=True))

    updated = update_talent_status(db, person.id, "standby")

    assert updated is person
    assert wrote["called"] is False


def test_inline_talent_status_update_writes_when_changed(monkeypatch):
    from resource_service import update_talent_status

    person = SimpleNamespace(id=uuid4(), status="standby", updated_at=None)
    calls = []
    db = SimpleNamespace(flush=lambda: calls.append("flush"), commit=lambda: calls.append("commit"))
    monkeypatch.setattr("resource_service.get_talent", lambda *_args: person)
    monkeypatch.setattr("resource_service._sync_legacy_translator", lambda *_args: calls.append("sync"))

    updated = update_talent_status(db, person.id, "active")

    assert updated is person
    assert person.status == "active"
    assert person.updated_at is not None
    assert calls == ["flush", "sync", "commit"]


def test_inline_talent_name_update_preserves_other_profile_fields(monkeypatch):
    from resource_service import update_talent_name

    person = SimpleNamespace(
        id=uuid4(), full_name="错字姓名", primary_phone="13800138000",
        annotation_profile=SimpleNamespace(task_types=["音频标注"]), updated_at=None,
    )
    calls = []
    db = SimpleNamespace(flush=lambda: calls.append("flush"), commit=lambda: calls.append("commit"))
    monkeypatch.setattr("resource_service.get_talent", lambda *_args: person)
    monkeypatch.setattr("resource_service._sync_legacy_translator", lambda *_args: calls.append("sync"))

    updated = update_talent_name(db, person.id, "正确姓名")

    assert updated is person
    assert person.full_name == "正确姓名"
    assert person.primary_phone == "13800138000"
    assert person.annotation_profile.task_types == ["音频标注"]
    assert calls == ["flush", "sync", "commit"]


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
