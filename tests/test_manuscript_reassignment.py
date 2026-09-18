from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import manuscript_service
from manuscript_models import ManuscriptArrangement, ManuscriptDispatch
from manuscript_schemas import (
    ManuscriptAssignmentInput,
    ManuscriptMilestoneInput,
    ManuscriptReassignmentCreate,
)
from word_count_schemas import WordCountValues


class QueryStub:
    def __init__(self, value):
        self.value = value

    def options(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.value


class ReassignmentDbStub:
    def __init__(self, dispatch, source, *, replacement_exists=False, duplicate=False):
        self.dispatch = dispatch
        self.source = source
        self.arrangement_query_count = 0
        self.replacement_exists = replacement_exists
        self.duplicate = duplicate
        self.commit_count = 0

    def query(self, model):
        if model is ManuscriptDispatch:
            return QueryStub(self.dispatch)
        self.arrangement_query_count += 1
        values = {
            1: self.source,
            2: SimpleNamespace(id=uuid4()) if self.replacement_exists else None,
            3: SimpleNamespace(id=uuid4()) if self.duplicate else None,
        }
        return QueryStub(values.get(self.arrangement_query_count))

    def flush(self):
        for item in self.dispatch.arrangements:
            if item.id is None:
                item.id = uuid4()

    def commit(self):
        self.commit_count += 1


def _payload(translator_id, updated_at):
    return ManuscriptReassignmentCreate(
        expected_updated_at=updated_at,
        reason="原译员临时无法继续",
        replacement=ManuscriptAssignmentInput(
            translator_id=translator_id,
            planned=WordCountValues(words=1200),
            actual=WordCountValues(words=999),
            settlement_method="月结",
            translator_total_price=360,
            translation_scope="全文",
            email_subject="不应继承的标题",
            email_body="不应继承的正文",
            milestones=[
                ManuscriptMilestoneInput(
                    milestone_type="final",
                    name="译员交稿_全稿预定时间",
                    sequence_no=1,
                    planned_at=datetime(2026, 9, 20, 18, 0),
                )
            ],
        ),
    )


def _state(status="sent"):
    now = datetime(2026, 9, 18, 10, 0)
    source = SimpleNamespace(
        id=uuid4(),
        dispatch_id=uuid4(),
        entity_type="project",
        translation_project_id=uuid4(),
        sub_order_id=None,
        translator_id=uuid4(),
        translator_name_snapshot="原译员",
        status=status,
        updated_at=now,
        sent_at=now if status == "sent" else None,
        smtp_message_id="<old-message@example.com>" if status == "sent" else None,
    )
    dispatch = SimpleNamespace(
        id=source.dispatch_id,
        entity_type="project",
        translation_project_id=source.translation_project_id,
        sub_order_id=None,
        status="sent" if status == "sent" else "ready",
        confirmed_at=now,
        arrangements=[source],
        updated_at=now,
    )
    project = SimpleNamespace(
        id=source.translation_project_id,
        project_status="sent_to_translator",
        updated_at=now,
    )
    return dispatch, source, project


def _prepare_service(monkeypatch, project):
    replacement_holder = {}

    def create_line(_db, _dispatch, assignment, _user, _values):
        replacement = SimpleNamespace(
            id=None,
            entity_type="project",
            translation_project_id=project.id,
            sub_order_id=None,
            translator_id=assignment.translator_id,
            order_no_snapshot="TP-260918-001",
            project_name_snapshot="测试项目",
            translator_name_snapshot="新译员",
            settlement_method=assignment.settlement_method,
            status="draft",
            email_subject=None,
            email_body=None,
            milestones=[],
            selected_files=[],
        )
        replacement_holder["value"] = replacement
        return replacement

    monkeypatch.setattr(manuscript_service, "_load_entity", lambda *_args: (project, None))
    monkeypatch.setattr(manuscript_service, "_ensure_can_manage_manuscript", lambda *_args: None)
    monkeypatch.setattr(manuscript_service, "_get_project_dispatch_path", lambda *_args: None)
    monkeypatch.setattr(
        manuscript_service,
        "_entity_values",
        lambda *_args, **_kwargs: {
            "order_no": "TP-260918-001",
            "project_name": "测试项目",
            "dispatch_path": None,
            "customer_deadline_time": None,
        },
    )
    monkeypatch.setattr(manuscript_service, "_create_arrangement_line", create_line)
    monkeypatch.setattr(manuscript_service, "replace_arrangement_values", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        manuscript_service,
        "_sync_order_status",
        lambda _db, target, _sub: manuscript_service._set_order_status(
            target, None, "translator_assigned"
        ),
    )
    monkeypatch.setattr(
        manuscript_service,
        "_load_dispatch_for_actor",
        lambda _db, _id, _user: _db.dispatch,
    )
    return replacement_holder


@pytest.mark.parametrize("status", ["ready", "failed", "sent"])
def test_reassign_keeps_history_and_creates_ready_replacement(monkeypatch, status):
    dispatch, source, project = _state(status)
    holder = _prepare_service(monkeypatch, project)
    db = ReassignmentDbStub(dispatch, source)
    new_translator_id = uuid4()

    result, replacement_id = manuscript_service.reassign_arrangement(
        db,
        dispatch.id,
        source.id,
        _payload(new_translator_id, source.updated_at),
        SimpleNamespace(id=uuid4(), full_name="项目助理", username="assistant"),
    )

    replacement = holder["value"]
    assert result is dispatch
    assert replacement_id == replacement.id
    assert source.status == "cancelled"
    assert source.smtp_message_id == ("<old-message@example.com>" if status == "sent" else None)
    assert replacement.status == "ready"
    assert replacement.translator_id == new_translator_id
    assert replacement.reassigned_from_arrangement_id == source.id
    assert replacement.reassignment_reason == "原译员临时无法继续"
    assert replacement.email_subject is None
    assert replacement.email_body is None
    assert dispatch.status == "ready"
    assert project.project_status == "translator_assigned"
    assert db.commit_count == 1


def test_reassign_rejects_existing_active_translator(monkeypatch):
    dispatch, source, project = _state("sent")
    _prepare_service(monkeypatch, project)
    db = ReassignmentDbStub(dispatch, source, duplicate=True)

    with pytest.raises(ValueError, match="已在当前批次"):
        manuscript_service.reassign_arrangement(
            db,
            dispatch.id,
            source.id,
            _payload(uuid4(), source.updated_at),
            SimpleNamespace(id=uuid4(), full_name=None, username="assistant"),
        )

    assert source.status == "sent"
    assert db.commit_count == 0


def test_reassign_rejects_already_reassigned_source(monkeypatch):
    dispatch, source, project = _state("sent")
    _prepare_service(monkeypatch, project)
    db = ReassignmentDbStub(dispatch, source, replacement_exists=True)

    with pytest.raises(ValueError, match="已经改派"):
        manuscript_service.reassign_arrangement(
            db,
            dispatch.id,
            source.id,
            _payload(uuid4(), source.updated_at),
            SimpleNamespace(id=uuid4(), full_name=None, username="assistant"),
        )


def test_cancel_dispatch_uses_historical_sent_time(monkeypatch):
    dispatch, source, _project = _state("sent")
    source.status = "cancelled"
    dispatch.status = "ready"
    dispatch.arrangements.append(SimpleNamespace(status="ready", sent_at=None))
    monkeypatch.setattr(manuscript_service, "_load_dispatch", lambda *_args: dispatch)

    with pytest.raises(ValueError, match="包含已发送明细"):
        manuscript_service.cancel_dispatch(
            SimpleNamespace(),
            dispatch.id,
            SimpleNamespace(),
        )
