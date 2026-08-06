from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from models import EmployeeLeave
from routers import leave as leave_router


class FakeLeaveOverviewQuery:
    def __init__(self):
        self.filter_calls = []

    def join(self, *_args):
        return self

    def options(self, *_args):
        return self

    def filter(self, *criteria):
        self.filter_calls.append(criteria)
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return []


class FakeDb:
    def __init__(self):
        self.leave_query = FakeLeaveOverviewQuery()

    def query(self, model):
        assert model is EmployeeLeave
        return self.leave_query


@pytest.mark.parametrize("department", ["项目部", None])
def test_leave_overview_is_company_wide_for_authenticated_users(department, monkeypatch):
    db = FakeDb()
    current_user = SimpleNamespace(id=uuid4(), department=department)
    monkeypatch.setattr(leave_router, "joinedload", lambda _relationship: object())

    result = leave_router.get_leave_overview(
        start_date=datetime(2026, 8, 6, 0, 0),
        end_date=datetime(2026, 9, 5, 0, 0),
        db=db,
        current_user=current_user,
    )

    assert result == []
    assert len(db.leave_query.filter_calls) == 1
    assert len(db.leave_query.filter_calls[0]) == 2
