"""只读导入预览的日期、键和状态拆分边界。"""
from types import SimpleNamespace

from resource_development_import_preview import action_preview, key, match_languages, parse_date


def test_invalid_excel_date_is_not_normalized():
    assert parse_date("20261026") == "2026-10-26"
    assert parse_date("20261039") == ""


def test_existing_key_ignores_excel_numeric_cell_type():
    old = {"日期": 20260909, "开拓人/HR": "王露", "姓名": "张三", "语种": "粤语", "来源": "Boss", "对接账号": "HR6微信", "备注：微信号/手机号": 13800000000}
    new = {**old, "日期": "20260909", "来源": "boss", "备注：微信号/手机号": "13800000000"}
    assert key(old) == key(new)


def test_request_marker_is_not_counted_as_added_friend():
    user = SimpleNamespace(is_active=True)
    action = action_preview("1022-黎涛已发请求", "已加微信", "2026-10-21", {"黎涛": user})
    assert action["date"] == "2026-10-22"
    assert action["status"] == "一次请求"
    assert not action["issues"]


def test_inactive_operator_requires_review():
    user = SimpleNamespace(is_active=False)
    action = action_preview("0926-景瀚", "已邀进群", "2026-09-20", {"景瀚": user})
    assert action["status"] == "已拉群"
    assert "状态操作人已停用" in action["issues"]


def test_multilanguage_keeps_unmatched_original():
    matched, unmatched = match_languages("粤语/西语母语、未知方向", {"粤语", "西班牙语"})
    assert matched == ["粤语", "西班牙语"]
    assert unmatched == ["未知方向"]
