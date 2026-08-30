from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

import crud
from models import TranslationProject, TranslationSubOrder
from routers import sub_orders as sub_order_router
from schemas import TranslationSubOrderBulkCreate


def test_bulk_schema_trims_names_and_rejects_invalid_values():
    payload = TranslationSubOrderBulkCreate(
        parent_project_id=uuid4(),
        sub_project_names=["\ufeff  文件一.docx  ", "文件二.pdf"],
    )
    assert payload.sub_project_names == ["文件一.docx", "文件二.pdf"]

    with pytest.raises(ValidationError):
        TranslationSubOrderBulkCreate(parent_project_id=uuid4(), sub_project_names=["   "])
    with pytest.raises(ValidationError):
        TranslationSubOrderBulkCreate(parent_project_id=uuid4(), sub_project_names=["a" * 256])
    with pytest.raises(ValidationError):
        TranslationSubOrderBulkCreate(
            parent_project_id=uuid4(),
            sub_project_names=[f"文件-{index}" for index in range(501)],
        )


def test_partition_sub_project_names_skips_existing_and_request_duplicates():
    accepted, skipped = crud.partition_sub_project_names(
        ["New.docx", " new.DOCX ", "已有.pdf", "另一个.txt"],
        [" 已有.PDF "],
    )

    assert accepted == ["New.docx", "另一个.txt"]
    assert skipped == [
        {"name": " new.DOCX ", "reason": "本次导入内容中名称重复"},
        {"name": "已有.pdf", "reason": "当前母订单已存在同名子订单"},
    ]


class _FakeQuery:
    def __init__(self, db, model):
        self.db = db
        self.model = model

    def filter(self, *_args):
        return self

    def with_for_update(self):
        self.db.locked = True
        return self

    def first(self):
        return self.db.parent if self.model is TranslationProject else None

    def all(self):
        return self.db.existing if self.model is TranslationSubOrder else []


class _FakeDb:
    def __init__(self):
        self.parent = SimpleNamespace(id=uuid4())
        self.existing = [SimpleNamespace(sub_project_name="已有.txt")]
        self.locked = False
        self.commit_count = 0
        self.refreshed = []

    def query(self, model):
        return _FakeQuery(self, model)

    def commit(self):
        self.commit_count += 1

    def refresh(self, item):
        self.refreshed.append(item)

    def rollback(self):
        self.rolled_back = True


def test_bulk_service_locks_parent_and_commits_once(monkeypatch):
    db = _FakeDb()
    parent_project_id = db.parent.id
    payload = TranslationSubOrderBulkCreate(
        parent_project_id=parent_project_id,
        sub_project_names=["A.docx", "已有.TXT", "B.pdf"],
        defaults={"priority": "高"},
    )
    received = []

    def fake_create(_db, sub_order, idempotency_key=None):
        received.append(sub_order)
        return SimpleNamespace(id=uuid4(), sub_project_name=sub_order.sub_project_name)

    monkeypatch.setattr(crud, "_create_sub_order_in_transaction", fake_create)
    monkeypatch.setattr(crud, "_sync_project_name_with_sub_order_count", lambda *_args: None)
    monkeypatch.setattr(crud, "_attach_manuscript_assignees", lambda *_args, **_kwargs: None)

    created, skipped = crud.create_sub_orders_bulk(db, payload, created_by=uuid4())

    assert db.locked is True
    assert db.commit_count == 1
    assert [item.sub_project_name for item in created] == ["A.docx", "B.pdf"]
    assert [item.priority for item in received] == ["高", "高"]
    assert skipped == [{"name": "已有.TXT", "reason": "当前母订单已存在同名子订单"}]


def test_sub_order_creation_initializes_matrix_and_workflow_in_same_transaction(monkeypatch):
    parent_project_id = uuid4()
    created_by = uuid4()
    db = SimpleNamespace(add=lambda _item: None, flush=lambda: None)
    matrix_calls = []
    workflow_calls = []

    monkeypatch.setattr(crud, "generate_sub_order_no", lambda *_args: "TP-260830-001.001")
    monkeypatch.setattr(crud, "_validate_written_translator", lambda *_args: None)
    monkeypatch.setattr(crud, "TranslationSubOrder", lambda **values: SimpleNamespace(id=uuid4(), **values))
    monkeypatch.setattr(
        "word_count_service.save_created_entity_matrix",
        lambda *args, **kwargs: matrix_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        "workflow_crud.init_workflow",
        lambda *args, **kwargs: workflow_calls.append((args, kwargs)),
    )

    payload = TranslationSubOrderBulkCreate(
        parent_project_id=parent_project_id,
        sub_project_names=["合同正文.docx"],
    )
    sub_order = crud._create_sub_order_in_transaction(
        db,
        crud.TranslationSubOrderCreate(
            parent_project_id=parent_project_id,
            sub_project_name=payload.sub_project_names[0],
            created_by=created_by,
        ),
    )

    assert sub_order.sub_order_no == "TP-260830-001.001"
    assert sub_order.sub_project_name == "合同正文.docx"
    assert matrix_calls[0][0][1] == "suborder"
    assert matrix_calls[0][1]["updated_by"] == created_by
    assert workflow_calls == [((db,), {"sub_order_id": sub_order.id, "commit": False})]


def test_bulk_endpoint_rolls_back_all_changes_when_creation_fails(monkeypatch):
    db = _FakeDb()
    db.rolled_back = False
    payload = TranslationSubOrderBulkCreate(
        parent_project_id=db.parent.id,
        sub_project_names=["A.docx", "B.docx"],
    )
    monkeypatch.setattr(
        sub_order_router,
        "create_sub_orders_bulk",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("workflow failed")),
    )

    with pytest.raises(Exception) as exc_info:
        sub_order_router.create_sub_orders_bulk_endpoint(
            payload,
            db,
            SimpleNamespace(id=uuid4()),
        )

    assert exc_info.value.status_code == 500
    assert db.rolled_back is True
    assert db.commit_count == 0
