import datetime
from types import SimpleNamespace
from uuid import uuid4

import crud


class QueryStub:
    def __init__(self, rows):
        self.rows = rows

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows


class DbStub:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return QueryStub(self.rows)


def test_translation_project_assignee_exposes_final_planned_time(monkeypatch):
    project_id = uuid4()
    return_time = datetime.datetime(2026, 9, 8, 18, 0)
    arrangement = SimpleNamespace(
        id=uuid4(),
        dispatch_id=uuid4(),
        translation_project_id=project_id,
        sub_order_id=None,
        translator_id=uuid4(),
        translator_name_snapshot="测试译员",
        cooperation_type_snapshot="freelance",
        status="ready",
        translation_scope="全文",
        planned_delivery_at=return_time,
    )
    project = SimpleNamespace(id=project_id, sub_orders=[])
    monkeypatch.setattr(crud, "_attach_word_count_matrices", lambda *args, **kwargs: None)

    crud._attach_manuscript_assignees(DbStub([arrangement]), projects=[project])

    assert project.assigned_translators[0]["translator_return_time"] == return_time
