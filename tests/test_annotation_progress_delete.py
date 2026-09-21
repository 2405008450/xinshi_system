from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import recruitment_models  # noqa: F401  确保跨项目工作台关系在 SQLAlchemy 配置前完成注册
import annotation_ops_service
from annotation_models import AnnotationProject
from annotation_ops_models import AnnotationProjectStatusHistory
from annotation_ops_schemas import StatusHistoryProgressDelete
from annotation_ops_service import delete_progress_history


class ProgressDeleteDb:
    def __init__(self, row, project):
        self.row = row
        self.project = project
        self.deleted = []
        self.committed = False

    def get(self, model, key):
        if model is AnnotationProjectStatusHistory and key == self.row.id:
            return self.row
        if model is AnnotationProject and key == self.project.id:
            return self.project
        return None

    def delete(self, value):
        self.deleted.append(value)

    def commit(self):
        self.committed = True


def progress_row(entry_kind="progress"):
    project_id = uuid4()
    now = datetime(2026, 9, 21, 10, 30)
    return SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        from_status="trial_in_progress",
        to_status="trial_in_progress" if entry_kind == "progress" else "trial_passed",
        effective_on=now,
        changed_at=now,
        changed_by=uuid4(),
        change_note="等待客户补充测试数据",
        entry_kind=entry_kind,
        updated_at=now,
        updated_by=None,
    )


def test_progress_delete_requires_non_blank_reason():
    with pytest.raises(ValueError, match="请填写删除原因"):
        StatusHistoryProgressDelete(reason="   ")

    payload = StatusHistoryProgressDelete(reason="  内容录入错误  ")
    assert payload.reason == "内容录入错误"


def test_delete_progress_keeps_audit_snapshot(monkeypatch):
    row = progress_row()
    project = SimpleNamespace(id=row.project_id, order_no="AP-260921-001", project_name="语音标注")
    db = ProgressDeleteDb(row, project)
    captured = {}

    def fake_record(_db, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(annotation_ops_service, "record_project_operation", fake_record)
    monkeypatch.setattr(annotation_ops_service, "list_status_history", lambda _db, project_id: [project_id])

    result = delete_progress_history(
        db,
        row.id,
        StatusHistoryProgressDelete(reason="录入到错误项目", expected_updated_at=row.updated_at),
        uuid4(),
    )

    assert result == [row.project_id]
    assert db.deleted == [row]
    assert db.committed is True
    assert captured["operation_type"] == "progress_delete"
    assert captured["operation_source"] == "progress_record_delete"
    assert captured["change_reason"] == "录入到错误项目"
    assert captured["snapshot_extra"]["deleted_progress_record"]["change_note"] == row.change_note


def test_status_transition_cannot_be_deleted(monkeypatch):
    row = progress_row("status")
    project = SimpleNamespace(id=row.project_id, order_no="AP-260921-002", project_name="语音标注")
    db = ProgressDeleteDb(row, project)
    monkeypatch.setattr(
        annotation_ops_service,
        "record_project_operation",
        lambda *_args, **_kwargs: pytest.fail("状态流转记录不应写入删除审计"),
    )

    with pytest.raises(ValueError, match="状态流转记录不可删除"):
        delete_progress_history(
            db,
            row.id,
            StatusHistoryProgressDelete(reason="不应允许"),
            uuid4(),
        )

    assert db.deleted == []
    assert db.committed is False
