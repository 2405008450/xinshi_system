from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from routers import auth


@pytest.mark.parametrize("role_name", ["超级管理员", "admin", "项目经理", "项目助理"])
def test_manuscript_allowed_roles_pass_role_dependency(monkeypatch, role_name):
    user = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(
        auth,
        "get_user_roles_with_role_names",
        lambda _db, _user_id: [role_name],
    )

    dependency = auth.require_any_role("项目经理", "项目助理")

    assert dependency(current_user=user, db=object()) is user


def test_other_role_is_rejected_by_manuscript_role_dependency(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(
        auth,
        "get_user_roles_with_role_names",
        lambda _db, _user_id: ["项目专员"],
    )

    dependency = auth.require_any_role("项目经理", "项目助理")

    with pytest.raises(HTTPException) as exc_info:
        dependency(current_user=user, db=object())

    assert exc_info.value.status_code == 403

