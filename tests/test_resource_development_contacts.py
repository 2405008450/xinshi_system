"""联系方式拆分防止渠道串列、占位词和第三方 ID 误入本人字段。"""
from types import SimpleNamespace

from resource_development_contacts import classify_contact
from tools.reconcile_resource_development_contacts_20261026 import proposed_changes


def test_labeled_xiaohongshu_stays_out_of_phone_and_wechat():
    parsed = classify_contact("18724142714（小红书号）")
    assert parsed["xiaohongshu"] == "18724142714"
    assert parsed["phone"] == parsed["wechat"] == ""
    old = SimpleNamespace(phone="18724142714", wechat="18724142714（小红书号）", xiaohongshu="")
    changes, conflicts = proposed_changes(old, "18724142714（小红书号）", parsed)
    assert not conflicts
    assert changes["phone"]["after"] == ""
    assert changes["wechat"]["after"] == ""
    assert changes["xiaohongshu"]["after"] == "18724142714"


def test_missing_and_third_party_are_not_person_contacts():
    for raw in ("未提供", "他推的朋友id：dionvdam（陈大伟）"):
        parsed = classify_contact(raw)
        assert not any(parsed[field] for field in ("phone", "wechat", "xiaohongshu"))
        assert parsed["other"] == raw


def test_explicit_phone_and_wechat_split():
    parsed = classify_contact("电话：15858725540微信：Ix0814xI")
    assert parsed["phone"] == "15858725540"
    assert parsed["wechat"] == "Ix0814xI"


def test_existing_distinct_contact_is_kept():
    parsed = classify_contact("JamieFromTheUK（小红书号）")
    old = SimpleNamespace(phone="", wechat="existing_wechat", xiaohongshu="")
    changes, conflicts = proposed_changes(old, "JamieFromTheUK（小红书号）", parsed)
    assert not conflicts
    assert "wechat" not in changes
    assert changes["xiaohongshu"]["after"] == "JamieFromTheUK"
