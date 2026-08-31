from datetime import datetime

from crud import _is_auto_project_name, build_auto_project_name


def test_translation_project_name_contains_direction_and_deadline():
    name = build_auto_project_name(
        "测试客户",
        current_time=datetime(2026, 8, 31, 9, 0),
        language_pair="中文→英文",
        customer_deadline_time=datetime(2026, 9, 2, 18, 30),
    )

    assert name == "测试客户-260831-中文→英文-20260902-18:30回稿"
    assert _is_auto_project_name(name, "测试客户") is True


def test_translation_project_name_keeps_batch_suffix():
    name = build_auto_project_name(
        "测试客户",
        sub_order_count=2,
        current_time=datetime(2026, 8, 31, 9, 0),
        language_pair="中文-英文",
        customer_deadline_time="2026-09-02 18:30:00",
    )

    assert name == "测试客户-260831-中文-英文-20260902-18:30回稿-2批"
    assert _is_auto_project_name(name, "测试客户") is True


def test_legacy_auto_project_name_is_still_recognized():
    assert _is_auto_project_name("测试客户-260831", "测试客户") is True
    assert _is_auto_project_name("测试客户-260831-2批", "测试客户") is True
    assert _is_auto_project_name(
        "测试客户-260831-中文→英文-20260902-1830回稿", "测试客户"
    ) is True
    assert _is_auto_project_name("测试客户-手工名称", "测试客户") is False
