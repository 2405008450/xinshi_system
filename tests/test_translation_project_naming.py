from datetime import datetime
from types import SimpleNamespace

from crud import (
    _is_auto_project_name,
    _sync_project_name_with_sub_order_count,
    build_auto_project_name,
)


def test_translation_project_name_matches_business_example():
    assert build_auto_project_name(
        "广州学在华留学咨询",
        language_pair="法语（法国）→中文（简体）",
        customer_deadline_time=datetime(2026, 9, 1, 16, 0),
    ) == "广州学在华留学咨询，法译中，9月1日16点回稿"


def test_translation_project_name_contains_direction_and_deadline():
    name = build_auto_project_name(
        "测试客户",
        current_time=datetime(2026, 8, 31, 9, 0),
        language_pair="法语（法国）→中文（简体）",
        customer_deadline_time=datetime(2026, 9, 2, 18, 30),
    )

    assert name == "测试客户，法译中，9月2日18点回稿"
    assert _is_auto_project_name(name, "测试客户") is True


def test_translation_project_name_keeps_batch_suffix():
    name = build_auto_project_name(
        "测试客户",
        sub_order_count=2,
        current_time=datetime(2026, 8, 31, 9, 0),
        language_pair="中文（简体）→英语（美国）",
        customer_deadline_time="2026-09-02 18:30:00",
    )

    assert name == "测试客户，中译英，9月2日18点回稿，2批"
    assert _is_auto_project_name(name, "测试客户") is True


def test_legacy_auto_project_name_is_still_recognized():
    assert _is_auto_project_name(
        "测试客户，法译中，9月2日18点回稿", "测试客户"
    ) is True
    assert _is_auto_project_name(
        "测试客户-中文→英文-20260902-1830回", "测试客户"
    ) is True
    assert _is_auto_project_name("测试客户-260831", "测试客户") is True
    assert _is_auto_project_name("测试客户-260831-2批", "测试客户") is True
    assert _is_auto_project_name(
        "测试客户-260831-中文→英文-20260902-1830回稿", "测试客户"
    ) is True
    assert _is_auto_project_name("测试客户-手工名称", "测试客户") is False


def test_non_translation_fallback_keeps_date_format():
    assert build_auto_project_name(
        "测试客户", current_time=datetime(2026, 8, 31, 9, 0)
    ) == "测试客户-260831"


def test_sub_order_count_sync_uses_parent_client_for_project_name(monkeypatch):
    project = SimpleNamespace(
        id="project-id",
        client=SimpleNamespace(client_short_name="母客户"),
        sub_client=SimpleNamespace(client_short_name="子客户"),
        project_name="母客户-260831",
        language_pair=None,
        customer_deadline_time=None,
    )

    class FakeQuery:
        def __init__(self, *, first_value=None, scalar_value=None):
            self.first_value = first_value
            self.scalar_value = scalar_value

        def options(self, *_args):
            return self

        def filter(self, *_args):
            return self

        def first(self):
            return self.first_value

        def scalar(self):
            return self.scalar_value

    queries = iter((FakeQuery(first_value=project), FakeQuery(scalar_value=2)))
    db = SimpleNamespace(query=lambda *_args: next(queries))
    captured = {}

    def fake_build(client_short_name, sub_order_count, *_args):
        captured["client_short_name"] = client_short_name
        captured["sub_order_count"] = sub_order_count
        return f"{client_short_name}-{sub_order_count}批"

    monkeypatch.setattr("crud.build_auto_project_name", fake_build)
    monkeypatch.setattr("crud._is_auto_project_name", lambda *_args: True)

    _sync_project_name_with_sub_order_count(db, project.id)

    assert captured == {"client_short_name": "母客户", "sub_order_count": 2}
    assert project.project_name == "母客户-2批"
