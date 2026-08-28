import datetime as dt
from types import SimpleNamespace
from unittest.mock import MagicMock

import crud


class _FixedDateTime(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 8, 27, tzinfo=tz)


class _QueryStub:
    def __init__(self, record=None):
        self.record = record

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.record


class _DbStub:
    def __init__(self, record=None, records=None):
        self.record = record
        self.records = iter(records) if records is not None else None

    def query(self, *args, **kwargs):
        if self.records is not None:
            return _QueryStub(next(self.records))
        return _QueryStub(self.record)


def test_generate_client_code_uses_compact_date(monkeypatch):
    monkeypatch.setattr(crud.dt, "datetime", _FixedDateTime)

    code = crud.generate_client_code(_DbStub())

    assert code == "CL-260827-001"


def test_generate_client_code_increments_same_day_sequence(monkeypatch):
    monkeypatch.setattr(crud.dt, "datetime", _FixedDateTime)
    last_client = SimpleNamespace(client_code="CL-260827-002")

    code = crud.generate_client_code(_DbStub(last_client))

    assert code == "CL-260827-003"


def test_generate_client_code_continues_legacy_same_day_sequence(monkeypatch):
    monkeypatch.setattr(crud.dt, "datetime", _FixedDateTime)
    legacy_client = SimpleNamespace(client_code="CL-26-0827-004")

    code = crud.generate_client_code(_DbStub(records=[None, legacy_client]))

    assert code == "CL-260827-005"


def test_generate_sub_client_code_inherits_compact_client_code(monkeypatch):
    parent_id = object()
    parent = SimpleNamespace(client_code="CL-260827-003")
    monkeypatch.setattr(crud, "get_client", lambda db, current_id: parent)

    code = crud.generate_sub_client_code(_DbStub(), parent_id)

    assert code == "CL-260827-003.001"


def test_get_clients_defaults_to_newest_first():
    db = MagicMock()
    query = MagicMock()
    ordered_query = MagicMock()
    db.query.return_value.options.return_value = query
    query.order_by.return_value = ordered_query
    ordered_query.offset.return_value.limit.return_value.all.return_value = []

    crud.get_clients(db, skip=0, limit=10)

    query.order_by.assert_called_once()
    order_columns = query.order_by.call_args.args
    assert str(order_columns[0]) == "client.created_at DESC"
    assert str(order_columns[1]) == "client.id DESC"
