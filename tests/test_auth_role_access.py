import inspect
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from routers import auth
from routers.annotation_projects import router as annotation_projects_router


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


def test_annotation_order_no_route_requires_write_and_sensitive_permissions():
    route = next(
        item
        for item in annotation_projects_router.routes
        if getattr(item, "path", None)
        == "/projects/annotation/{project_id}/order-no"
    )
    dependency_settings = [
        inspect.getclosurevars(dependency.call).nonlocals
        for dependency in route.dependant.dependencies
    ]

    assert any(
        settings.get("write_permission") == "projects:write"
        for settings in dependency_settings
    )
    assert any(
        settings.get("permission_code") == "projects:order_no:write"
        for settings in dependency_settings
    )


@pytest.mark.parametrize(
    ("granted_permissions", "expected_status"),
    [
        ({"projects:write"}, 403),
        ({"projects:order_no:write"}, 403),
        ({"projects:write", "projects:order_no:write"}, 200),
        ({"*"}, 200),
    ],
)
def test_annotation_order_no_permission_combination(
    monkeypatch, granted_permissions, expected_status
):
    user = SimpleNamespace(id=uuid4())
    app = FastAPI()

    @app.patch(
        "/permission-probe",
        dependencies=[
            Depends(auth.require_module_access("projects:read", "projects:write")),
            Depends(auth.require_permission("projects:order_no:write")),
        ],
    )
    def permission_probe():
        return {"ok": True}

    app.dependency_overrides[auth.get_current_user] = lambda: user
    app.dependency_overrides[auth.get_db] = lambda: object()
    monkeypatch.setattr(
        auth,
        "user_has_permission",
        lambda _db, _user_id, permission_code: (
            "*" in granted_permissions or permission_code in granted_permissions
        ),
    )

    with TestClient(app) as client:
        response = client.patch("/permission-probe")

    assert response.status_code == expected_status
