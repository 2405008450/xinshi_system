from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from crud import normalize_user_email
from routers import users as users_router
from schemas import AppUserCreate, AppUserUpdate


class _DbStub:
    def __init__(self):
        self.rollback_called = False

    def rollback(self):
        self.rollback_called = True


def test_normalize_user_email_ignores_case_and_surrounding_spaces():
    assert normalize_user_email("  User.Name@Example.COM  ") == "user.name@example.com"
    assert normalize_user_email("") is None
    assert normalize_user_email(None) is None


def test_create_user_rejects_email_already_bound(monkeypatch):
    db = _DbStub()
    monkeypatch.setattr(users_router, "get_user_by_username", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        users_router,
        "get_user_by_email",
        lambda *_args, **_kwargs: SimpleNamespace(id=uuid4()),
    )

    with pytest.raises(HTTPException) as exc_info:
        users_router.create_user_endpoint(
            AppUserCreate(
                username="new-user",
                password="test-password",
                email="Bound@Example.com",
            ),
            db,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == users_router.EMAIL_ALREADY_BOUND_DETAIL


def test_update_user_excludes_current_user_but_rejects_another_owner(monkeypatch):
    db = _DbStub()
    user_id = uuid4()
    calls = []

    def fake_get_by_email(_db, email, *, exclude_user_id=None):
        calls.append((str(email), exclude_user_id))
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(users_router, "get_user_by_email", fake_get_by_email)

    with pytest.raises(HTTPException) as exc_info:
        users_router.update_user_endpoint(
            user_id,
            AppUserUpdate(email="BOUND@example.com"),
            db,
        )

    assert calls == [("BOUND@example.com", user_id)]
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == users_router.EMAIL_ALREADY_BOUND_DETAIL


def test_email_availability_passes_editing_user_as_exclusion(monkeypatch):
    db = _DbStub()
    user_id = uuid4()
    calls = []

    def fake_get_by_email(_db, email, *, exclude_user_id=None):
        calls.append((email, exclude_user_id))
        return None

    monkeypatch.setattr(users_router, "get_user_by_email", fake_get_by_email)

    result = users_router.check_user_email_availability(
        "Current@Example.com",
        user_id,
        db,
    )

    assert result == {"available": True}
    assert calls == [("Current@Example.com", user_id)]
