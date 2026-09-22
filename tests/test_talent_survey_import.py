from copy import deepcopy
from uuid import uuid4

import pytest

from tools.prepare_talent_survey import LanguageResolver, SOURCE, education_level, prepare
from tools.import_talent_survey import validate_plan
from resource_schemas import ResourcePersonCreate, ResourcePersonListResponse


def catalog():
    return {"languages": [{"id": str(uuid4()), "label": label, "code": None}
                          for label in ["英语", "中文（简体）", "日语", "法语", "粤语"]],
            "aliases": [], "people": []}


def survey_row():
    row = ["(空)"] * 22
    row[0:4] = ["测试人员", "sample-wechat", "女（ Female）", "30+"]
    row[6] = "广东"
    row[12:20] = ["粤语", "非常熟练（从小说到大）", "(空)", "English", "日语", "有Yes", "英语六级", "有Yes"]
    return row


def test_source_and_native_place_and_no_invented_age_or_annotation_language():
    plan = prepare([(2, survey_row())], catalog(), "a" * 64, "Sheet1")
    payload = validate_plan(plan)[0]
    assert payload.registration_source == SOURCE
    assert payload.native_place == "广东"
    assert payload.birth_date is None and payload.birth_year_month is None
    assert "30+" in payload.remarks
    assert payload.annotation_language_skills == []
    assert not any(x.role == "native" for x in payload.language_skills)
    assert {x.role for x in payload.language_skills} == {"foreign", "dialect_ethnic"}
    assert payload.certificates[0].material_received is False
    assert "sample-wechat" not in payload.remarks


def test_duplicate_rows_keep_distinct_idempotency_keys_and_both_marked():
    plan = prepare([(2, survey_row()), (3, survey_row())], catalog(), "a" * 64, "Sheet1")
    assert len(validate_plan(plan)) == 2
    assert plan["records"][0]["idempotency_key"] != plan["records"][1]["idempotency_key"]
    assert all("表内同名" in r["duplicate_matches"] for r in plan["records"])
    assert all("表内相同微信" in r["duplicate_matches"] for r in plan["records"])


def test_language_mixed_names_and_countries_do_not_infer_language():
    resolver = LanguageResolver(catalog())
    assert [x["label"] for x in resolver.resolve("English and Chinese")[0]] == ["英语", "中文（简体）"]
    assert resolver.resolve("Saudi Arabia")[0] == []
    assert resolver.resolve("广西大学")[0] == []
    assert resolver.resolve("I have a team that is fluent in English")[0] == []
    assert [x["label"] for x in resolver.resolve("巴西葡萄牙语（Brazilian Portuguese）")[0]] == ["葡萄牙语（巴西）"]


def test_student_education_not_mistaken_for_awarded_degree():
    assert education_level("本科毕业，硕士在读") is None
    assert education_level("Master degree") == "master"


def test_raw_dialect_and_qualification_preserved_and_no_contact_in_remarks():
    row = survey_row()
    row[12] = "某地乡音"
    plan = prepare([(2, row)], catalog(), "a" * 64, "Sheet1")
    assert plan["records"][0]["payload"]["dialects"] == ["某地乡音"]
    assert any(item["original"] == "某地乡音" for item in plan["language_review"])


def test_plan_tampering_cannot_add_annotation_language_or_change_source():
    plan = prepare([(2, survey_row())], catalog(), "a" * 64, "Sheet1")
    altered = deepcopy(plan)
    altered["records"][0]["payload"]["registration_source"] = "另一个来源"
    with pytest.raises(ValueError, match="约定"):
        validate_plan(altered)
    altered = deepcopy(plan)
    altered["records"][0]["idempotency_key"] = "bad-key"
    with pytest.raises(ValueError, match="幂等键"):
        validate_plan(altered)


def test_source_is_optional_trimmed_bounded_and_in_response():
    assert ResourcePersonCreate(full_name="测试").registration_source is None
    assert ResourcePersonCreate(full_name="测试", registration_source="  2609资源整合行动  ").registration_source == SOURCE
    assert "registration_source" in ResourcePersonListResponse.model_fields
    with pytest.raises(ValueError):
        ResourcePersonCreate(full_name="测试", registration_source="源" * 256)
