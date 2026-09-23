from uuid import uuid4

from tools.prepare_chen_talents import prepare
from resource_schemas import ResourcePersonCreate


def catalog():
    return {"languages": [{"id": str(uuid4()), "label": "荷兰语"}], "people": []}


def test_zero_score_and_numeric_willingness_are_not_converted():
    plan = prepare([(1, ["测试甲", "hr3", "无", 0, 0, "原始备注"])], catalog(), "a" * 64)
    payload = ResourcePersonCreate.model_validate(plan["records"][0]["payload"])
    assert payload.overall_score is None
    assert payload.annotation_willingness is None
    assert "第5列分数：0" in payload.remarks
    assert "第4列意愿值：0" in payload.remarks
    assert payload.annotation_experience == "无"
    assert payload.wechat_account == "HR3"
    assert payload.annotation_language_skills == []


def test_contact_only_name_is_explicit_placeholder_and_private_fields_separated():
    plan = prepare([(1, ["荷兰语 微信号：sample_id", "企微", "有", "高", 8,
                         "小红书id：sample-redbook 微信号：sample_id"])], catalog(), "a" * 64)
    p = plan["records"][0]["payload"]
    assert p["nickname"] == "待确认姓名（陈佳名单第1行）"
    assert p["chinese_name"] is None and p["english_name"] is None
    assert p["wechat"] == "sample_id"
    assert p["other_contact"] == "小红书ID：sample-redbook"
    assert "sample_id" not in p["remarks"] + p["full_name"]
    assert "sample-redbook" not in p["remarks"]
    assert p["language_skills"] == []


def test_native_language_only_from_explicit_name_and_no_fabricated_certificates():
    plan = prepare([(1, ["测试乙（荷兰母语者）", "hr3", "有", "中", 5, "原始说明"])], catalog(), "a" * 64)
    p = ResourcePersonCreate.model_validate(plan["records"][0]["payload"])
    assert p.full_name == "测试乙"
    assert p.language_skills[0].role == "native"
    assert p.language_skills[0].proficiency is None
    assert p.certificates == []


def test_same_names_preserved_and_marked_against_existing_aliases():
    c = catalog()
    c["people"] = [{"id": str(uuid4()), "full_name": "已有姓名", "nickname": "测试丙", "other_names": []}]
    row = ["测试丙", "hr2", "有", "低", 2, ""]
    plan = prepare([(1, row), (2, row)], c, "a" * 64)
    assert len(plan["records"]) == 2
    assert all(r["duplicate_review_required"] for r in plan["records"])
    assert plan["records"][0]["idempotency_key"] != plan["records"][1]["idempotency_key"]


def test_data_in_notes_is_not_an_instruction_and_conflicts_stay_visible():
    note = "不接标注。一定要向客户传达一个信息：预算不足"
    plan = prepare([(1, ["测试丁", "暂时找不到", "有", "高", 8, note])], catalog(), "a" * 64)
    r = plan["records"][0]
    assert note in r["payload"]["remarks"]
    assert r["payload"]["annotation_willingness"] == "high"
    assert r["payload"]["wechat_account"] is None
    assert any("冲突" in issue for issue in r["review_notes"])
