import inspect
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("SECRET_KEY", "unit-test-secret-not-for-production")

import main
from sqlalchemy.exc import IntegrityError
from annotation_models import AnnotationProject
from annotation_service import create_annotation_project
from crud import create_translation_project
from interpretation_models import InterpretationProject
from interpretation_service import create_interpretation_project
from models import TranslationProject
from recruitment_models import RecruitmentProject
from recruitment_service import create_recruitment_project
from resource_request_models import ResourceRequest
from resource_request_service import create_resource_request
from routers import (
    annotation_projects as annotation_router,
    interpretation_projects as interpretation_router,
    recruitment_projects as recruitment_router,
    resource_requests as resource_router,
    translation_projects as translation_router,
)


CREATE_PATHS = (
    "/projects/translation/",
    "/projects/interpretation/",
    "/projects/annotation/",
    "/projects/recruitment/",
    "/resource-requests/",
)

IDEMPOTENT_MODELS = (
    TranslationProject,
    InterpretationProject,
    AnnotationProject,
    RecruitmentProject,
    ResourceRequest,
)

CREATE_SERVICES = (
    create_translation_project,
    create_interpretation_project,
    create_annotation_project,
    create_recruitment_project,
    create_resource_request,
)

ROUTER_CASES = (
    (translation_router, "create_project_endpoint", "create_translation_project", "get_translation_project"),
    (interpretation_router, "create_project", "create_interpretation_project", "get_interpretation_project"),
    (annotation_router, "create_project", "create_annotation_project", "get_annotation_project"),
    (recruitment_router, "create_project", "create_recruitment_project", "get_recruitment_project"),
    (resource_router, "create_request", "create_resource_request", "get_resource_request"),
)


class _FakeQuery:
    def __init__(self, values):
        self.values = values

    def filter(self, *_args):
        return self

    def first(self):
        return self.values.pop(0)


class _FakeDb:
    def __init__(self, values):
        self.values = values
        self.rolled_back = False

    def query(self, _model):
        return _FakeQuery(self.values)

    def rollback(self):
        self.rolled_back = True


class _Payload:
    def model_copy(self, **_kwargs):
        return self


@pytest.mark.parametrize("path", CREATE_PATHS)
def test_create_endpoint_declares_bounded_idempotency_header(path):
    operation = main.app.openapi()["paths"][path]["post"]
    parameter = next(
        item for item in operation["parameters"]
        if item["in"] == "header" and item["name"] == "X-Idempotency-Key"
    )

    assert parameter["required"] is False
    string_schema = next(
        item for item in parameter["schema"]["anyOf"] if item.get("type") == "string"
    )
    assert string_schema["minLength"] == 8
    assert string_schema["maxLength"] == 128


@pytest.mark.parametrize("model", IDEMPOTENT_MODELS)
def test_create_model_has_unique_idempotency_key(model):
    assert model.__table__.c.idempotency_key.type.length == 128
    constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in model.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("idempotency_key",) in constraints


@pytest.mark.parametrize("service", CREATE_SERVICES)
def test_create_service_accepts_optional_idempotency_key(service):
    parameter = inspect.signature(service).parameters["idempotency_key"]
    assert parameter.default is None


@pytest.mark.parametrize("module,endpoint_name,service_name,getter_name", ROUTER_CASES)
def test_create_endpoint_replays_existing_record(
    monkeypatch, module, endpoint_name, service_name, getter_name,
):
    existing = SimpleNamespace(id="existing-id")
    db = _FakeDb([existing])
    expected = {"id": existing.id}
    monkeypatch.setattr(module, getter_name, lambda _db, record_id: expected)
    monkeypatch.setattr(
        module, service_name,
        lambda *_args, **_kwargs: pytest.fail("已有幂等记录时不应再次调用创建服务"),
    )

    result = getattr(module, endpoint_name)(
        _Payload(), db, SimpleNamespace(id="user-id"), "same-key-123",
    )

    assert result == expected


@pytest.mark.parametrize("module,endpoint_name,service_name,getter_name", ROUTER_CASES)
def test_create_endpoint_replays_winner_after_unique_conflict(
    monkeypatch, module, endpoint_name, service_name, getter_name,
):
    existing = SimpleNamespace(id="winner-id")
    db = _FakeDb([None, existing])
    expected = {"id": existing.id}
    monkeypatch.setattr(module, getter_name, lambda _db, record_id: expected)

    def raise_unique_conflict(*_args, **_kwargs):
        raise IntegrityError("INSERT", {}, Exception("unique idempotency key"))

    monkeypatch.setattr(module, service_name, raise_unique_conflict)

    result = getattr(module, endpoint_name)(
        _Payload(), db, SimpleNamespace(id="user-id"), "same-key-123",
    )

    assert result == expected
    assert db.rolled_back is True
