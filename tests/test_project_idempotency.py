import inspect
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("SECRET_KEY", "unit-test-secret-not-for-production")

import main
from sqlalchemy.exc import IntegrityError
from annotation_models import AnnotationProject
from annotation_service import create_annotation_project
from crud import (
    create_client,
    create_client_contact,
    create_sub_client,
    create_sub_order,
    create_translation_project,
)
from interpretation_models import InterpretationProject
from interpretation_service import create_interpretation_project
from models import Client, ClientContact, SubClient, TranslationProject, TranslationSubOrder
from recruitment_models import RecruitmentProject
from recruitment_service import create_recruitment_project
from resource_request_models import ResourceRequest
from resource_request_service import create_resource_request
from resource_models import ResourcePerson
from resource_service import create_talent
from routers import (
    annotation_projects as annotation_router,
    client_contacts as contact_router,
    clients as client_router,
    interpretation_projects as interpretation_router,
    recruitment_projects as recruitment_router,
    resource_requests as resource_router,
    sub_orders as sub_order_router,
    talents as talent_router,
    translation_projects as translation_router,
)


CREATE_PATHS = (
    "/projects/translation/",
    "/projects/interpretation/",
    "/projects/annotation/",
    "/projects/recruitment/",
    "/resource-requests/",
    "/clients/",
    "/clients/{client_id}/sub_clients",
    "/client-contacts/",
    "/talents/",
    "/sub-orders/",
)

IDEMPOTENT_MODELS = (
    TranslationProject,
    InterpretationProject,
    AnnotationProject,
    RecruitmentProject,
    ResourceRequest,
    Client,
    SubClient,
    ClientContact,
    ResourcePerson,
    TranslationSubOrder,
)

CREATE_SERVICES = (
    create_translation_project,
    create_interpretation_project,
    create_annotation_project,
    create_recruitment_project,
    create_resource_request,
    create_client,
    create_sub_client,
    create_client_contact,
    create_talent,
    create_sub_order,
)

ROUTER_CASES = (
    (translation_router, "create_project_endpoint", "create_translation_project", "get_translation_project", "user"),
    (interpretation_router, "create_project", "create_interpretation_project", "get_interpretation_project", "user"),
    (annotation_router, "create_project", "create_annotation_project", "get_annotation_project", "user"),
    (recruitment_router, "create_project", "create_recruitment_project", "get_recruitment_project", "user"),
    (resource_router, "create_request", "create_resource_request", "get_resource_request", "user"),
    (client_router, "create_client_endpoint", "create_client", "get_client", "plain"),
    (client_router, "create_sub_client_endpoint", "create_sub_client", "get_sub_client", "sub_client"),
    (contact_router, "create_client_contact_endpoint", "create_client_contact", "get_client_contact", "plain"),
    (talent_router, "create_talent_endpoint", "create_talent", "get_talent", "plain"),
    (sub_order_router, "create_sub_order_endpoint", "create_sub_order", "get_sub_order", "user"),
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
    parent_client_id = "parent-id"

    def model_copy(self, **_kwargs):
        return self


def _invoke_endpoint(module, endpoint_name, style, db):
    endpoint = getattr(module, endpoint_name)
    payload = _Payload()
    if style == "user":
        return endpoint(payload, db, SimpleNamespace(id="user-id"), "same-key-123")
    if style == "sub_client":
        return endpoint("parent-id", payload, db, "same-key-123")
    return endpoint(payload, db, "same-key-123")


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


@pytest.mark.parametrize("module,endpoint_name,service_name,getter_name,style", ROUTER_CASES)
def test_create_endpoint_replays_existing_record(
    monkeypatch, module, endpoint_name, service_name, getter_name, style,
):
    existing = SimpleNamespace(id="existing-id")
    db = _FakeDb([existing])
    expected = {"id": existing.id}
    monkeypatch.setattr(module, getter_name, lambda _db, record_id: expected)
    monkeypatch.setattr(
        module, service_name,
        lambda *_args, **_kwargs: pytest.fail("已有幂等记录时不应再次调用创建服务"),
    )

    result = _invoke_endpoint(module, endpoint_name, style, db)

    assert result == expected


@pytest.mark.parametrize("module,endpoint_name,service_name,getter_name,style", ROUTER_CASES)
def test_create_endpoint_replays_winner_after_unique_conflict(
    monkeypatch, module, endpoint_name, service_name, getter_name, style,
):
    existing = SimpleNamespace(id="winner-id")
    db = _FakeDb([None, existing])
    expected = {"id": existing.id}
    monkeypatch.setattr(module, getter_name, lambda _db, record_id: expected)

    def raise_unique_conflict(*_args, **_kwargs):
        raise IntegrityError("INSERT", {}, Exception("unique idempotency key"))

    monkeypatch.setattr(module, service_name, raise_unique_conflict)

    result = _invoke_endpoint(module, endpoint_name, style, db)

    assert result == expected
    assert db.rolled_back is True
