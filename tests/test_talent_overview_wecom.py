"""企微大群语义与事务回归，数据库测试仅在局域网显式启用并逐例回滚。"""

import os
from datetime import date
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from concurrency import StaleUpdateError
from talent_overview_wecom_schemas import (
    LanguageManagementWrite, WecomArchiveWrite, WecomCountVoid,
    WecomCountWrite, WecomGroupCreate, WecomGroupWrite,
)
import talent_overview_wecom_service as service


def test_inputs_reject_negative_fractional_counts_and_forged_operator():
    assert WecomCountWrite(expected_revision=1, statistics_date="2026-10-08", people_count=0).people_count == 0
    for value in [-1, 1.5, True, "12", None]:
        with pytest.raises(ValidationError):
            WecomCountWrite(expected_revision=1, statistics_date="2026-10-08", people_count=value)
    with pytest.raises(ValidationError):
        WecomGroupCreate(name="  ", is_built=False)
    with pytest.raises(ValidationError):
        WecomGroupCreate(name="拟建群", is_built=False, built_date="2026-10-08")
    with pytest.raises(ValidationError):
        WecomGroupCreate(name="测试群", is_built=True, operator_name="伪造用户")
    with pytest.raises(ValidationError):
        WecomCountVoid(expected_revision=1, reason="  ")


def test_summary_distinguishes_missing_zero_unbuilt_and_archived():
    groups = [SimpleNamespace(id=i, is_built=i != 2, archived=i == 3) for i in range(4)]
    latest = {0: [SimpleNamespace(people_count=0, statistics_date=date(2026, 10, 8))],
              2: [SimpleNamespace(people_count=100, statistics_date=date(2026, 10, 8))],
              3: [SimpleNamespace(people_count=200, statistics_date=date(2026, 10, 8))]}
    result = service.summarize_groups(groups, latest)
    assert result == dict(built_group_count=2, unbuilt_group_count=1, recorded_group_count=1,
                          people_count_total=0, latest_statistics_date=date(2026, 10, 8))
    assert service.summarize_groups(groups, {})["people_count_total"] is None


@pytest.fixture
def db():
    if os.getenv("RUN_TALENT_OVERVIEW_WECOM_DB_TESTS") != "1":
        pytest.skip("数据库回归仅允许局域网显式启用")
    import main  # noqa: F401，注册已有关系模型，不启动应用。
    from database import engine
    from sqlalchemy.orm import Session
    assert engine.url.host in {"localhost", "127.0.0.1", "192.168.31.144"}
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint", autoflush=False)
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def actor(db):
    from models import AppUser
    user = AppUser(id=uuid4(), username="wecom_test_" + uuid4().hex, full_name="企微测试人员", password_hash="not-a-login", is_active=True)
    db.add(user)
    db.flush()
    return user


def create(db, actor, **values):
    return service.create_group(db, "overview-001", WecomGroupCreate(**(dict(name="英语测试群", is_built=True) | values)), actor)


def register(db, actor, group, statistics_date, people_count):
    return service.register_count(db, group["id"], WecomCountWrite(expected_revision=group["revision"], statistics_date=statistics_date, people_count=people_count), actor)


def test_dates_same_day_backfill_void_and_audit_snapshots(db, actor):
    group = create(db, actor)
    group = register(db, actor, group, "2026-10-08", 120)
    group = register(db, actor, group, "2026-10-08", 125)
    assert (group["people_count"], group["change"]) == (125, 5)
    effective_id = group["latest_count_id"]
    group = register(db, actor, group, "2026-09-01", 70)
    assert group["people_count"] == 125 and group["latest_count_id"] == effective_id
    assert service.counts_page(db, group["id"])["total"] == 3
    group = service.void_count(db, group["id"], effective_id, WecomCountVoid(expected_revision=group["revision"], reason="重复统计，人数有误"), actor)
    assert group["people_count"] == 120 and group["change"] == 50
    records = service.counts_page(db, group["id"])["items"]
    invalid = next(row for row in records if row["id"] == effective_id)
    assert invalid["voided_by_name"] == "企微测试人员" and invalid["void_reason"]
    actor.full_name = "改名后的用户"
    db.flush()
    history = service.history_page(db, group_id=group["id"], page_size=2)
    assert history["total"] == 5 and len(history["items"]) == 2
    assert history["items"][0]["operator_name"] == "企微测试人员"


def test_language_and_group_notes_independent_revisions_and_unknown_language(db, actor):
    before = service.get_language_management(db, "overview-001")
    memo = service.save_language_management(db, "overview-001", LanguageManagementWrite(expected_revision=before["revision"], plan="拓展英语资源", remarks="语种备注"), actor)
    group = create(db, actor, plan="群运营计划", remarks="群备注")
    assert service.get_language_management(db, "overview-001")["plan"] == "拓展英语资源"
    assert group["plan"] == "群运营计划"
    with pytest.raises(StaleUpdateError):
        service.save_language_management(db, "overview-001", LanguageManagementWrite(expected_revision=before["revision"], plan="旧草稿"), actor)
    assert memo["revision"] == before["revision"] + 1
    with pytest.raises(LookupError):
        service.create_group(db, "row-unsaved", WecomGroupCreate(name="未保存语种的群", is_built=False), actor)


def test_unbuilt_to_built_archive_restore_and_count_conflict(db, actor):
    group = create(db, actor, is_built=False)
    with pytest.raises(ValueError):
        register(db, actor, group, "2026-10-08", 1)
    group = service.update_group(db, group["id"], WecomGroupWrite(expected_revision=group["revision"], name="英语项目群", is_built=True, built_date="2026-09-30", plan="已建计划"), actor)
    old = group
    group = register(db, actor, group, "2026-10-08", 0)
    with pytest.raises(StaleUpdateError):
        register(db, actor, old, "2026-10-08", 100)
    group = service.archive_group(db, group["id"], WecomArchiveWrite(expected_revision=group["revision"], archived=True), actor)
    assert group["archived"]
    assert group["id"] not in [item["id"] for item in service.list_groups(db, "overview-001")]
    assert group["id"] in [item["id"] for item in service.list_groups(db, "overview-001", True)]
    with pytest.raises(ValueError):
        register(db, actor, group, "2026-10-08", 1)
    group = service.archive_group(db, group["id"], WecomArchiveWrite(expected_revision=group["revision"], archived=False), actor)
    assert not group["archived"] and group["people_count"] == 0
    assert service.history_page(db, group_id=group["id"])["total"] == 5


def test_failed_audit_rolls_back_count_and_revision(db, actor):
    from routers.talent_overview_wecom import _call
    group = create(db, actor)
    db.commit()
    with patch.object(service, "_audit", side_effect=RuntimeError("模拟审计写入失败")):
        with pytest.raises(RuntimeError):
            _call(db, lambda: register(db, actor, group, "2026-10-08", 100), commit=True)
    assert service.get_group(db, group["id"])["revision"] == group["revision"]
    assert service.counts_page(db, group["id"])["total"] == 0


def test_overview_summary_does_not_change_source_totals(db, actor):
    from talent_overview_service import get_talent_overview
    before = get_talent_overview(db, include_wecom=True)
    group = register(db, actor, create(db, actor), "2026-10-08", 37)
    after = get_talent_overview(db, include_wecom=True)
    assert after["grand_total"] == before["grand_total"]
    assert after["column_totals"] == before["column_totals"]
    old = next(row for row in before["rows"] if row["overview_key"] == "overview-001")
    new = next(row for row in after["rows"] if row["overview_key"] == "overview-001")
    assert new["row_total"] == old["row_total"]
    assert new["wecom_summary"]["people_count_total"] == (old["wecom_summary"]["people_count_total"] or 0) + group["people_count"]
