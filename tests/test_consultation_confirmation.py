from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from models import Client
from routers.consultations import (
    ConsultationConfirmationFields,
    ConsultationConfirmationPreviewRequest,
    _build_subject_preview,
    _confirm_consultation_project,
    _confirmation_preview_values,
)
from schemas import TranslationProjectCreate


def test_translation_subject_uses_prefix_and_skips_empty_fields():
    parts, subject, missing = _build_subject_preview(
        project_type="translation",
        subject_prefix="  ***急***  ",
        order_no="TP-260812-001",
        client_short_name="信实客户",
        manager_contact=None,
        customer_order_no="不应进入笔译主题",
        project_name="信实客户-260812",
    )

    assert parts == ["***急***", "TP-260812-001", "信实客户", "信实客户-260812"]
    assert subject == "***急***，TP-260812-001，信实客户，信实客户-260812"
    assert missing == ["负责人联系方式"]


def test_interpretation_subject_contains_customer_identifier():
    parts, subject, missing = _build_subject_preview(
        project_type="interpretation",
        subject_prefix=None,
        order_no="IP-20260812-001",
        client_short_name="信实客户",
        manager_contact="张经理 13800000000",
        customer_order_no="PO-88",
        project_name="信实客户-260812",
    )

    assert parts[-2:] == ["PO-88", "信实客户-260812"]
    assert subject == "IP-20260812-001，信实客户，张经理 13800000000，PO-88，信实客户-260812"
    assert missing == []


def test_confirmation_prefix_length_and_translation_snapshot_schema():
    with pytest.raises(ValidationError):
        ConsultationConfirmationFields(
            expected_order_no="TP-260812-001",
            subject_prefix="急" * 51,
        )

    payload = TranslationProjectCreate(
        project_name="测试项目",
        email_subject_preview="TP-260812-001，测试客户，测试项目",
    )
    assert payload.email_subject_preview.endswith("测试项目")


class _ClientQuery:
    def __init__(self, client):
        self.client = client

    def filter(self, *_args):
        return self

    def first(self):
        return self.client


class _PreviewDb:
    def __init__(self, client):
        self.client = client

    def query(self, target):
        assert target is Client
        return _ClientQuery(self.client)


def test_preview_reads_manager_contact_from_linked_client(monkeypatch):
    client_id = uuid4()
    db = _PreviewDb(SimpleNamespace(
        id=client_id,
        client_short_name="客户简称",
        manager_contact="负责人联系方式",
    ))
    monkeypatch.setattr("routers.consultations.generate_order_no", lambda _db: "TP-260812-009")

    preview = _confirmation_preview_values(
        db,
        ConsultationConfirmationPreviewRequest(
            consultation_type="笔译项目",
            client_id=client_id,
            client_short_name="不能覆盖客户表简称",
            project_name="测试项目",
        ),
    )

    assert preview["client_short_name"] == "客户简称"
    assert preview["manager_contact"] == "负责人联系方式"
    assert preview["email_subject_preview"] == "TP-260812-009，客户简称，负责人联系方式，测试项目"


def test_preview_prefers_manager_contact_edited_in_consultation_form(monkeypatch):
    client_id = uuid4()
    db = _PreviewDb(SimpleNamespace(
        id=client_id,
        client_short_name="客户简称",
        manager_contact="客户表旧联系方式",
    ))
    monkeypatch.setattr("routers.consultations.generate_order_no", lambda _db: "TP-260812-011")

    preview = _confirmation_preview_values(
        db,
        ConsultationConfirmationPreviewRequest(
            consultation_type="笔译项目",
            client_id=client_id,
            manager_contact="表单新联系方式",
            project_name="测试项目",
        ),
    )

    assert preview["manager_contact"] == "表单新联系方式"
    assert preview["email_subject_preview"] == "TP-260812-011，客户简称，表单新联系方式，测试项目"


def test_order_number_conflict_stops_before_project_mutation(monkeypatch):
    consultation = SimpleNamespace(
        id=uuid4(), consultation_type="笔译项目", client_id=uuid4(), client_short_name="客户"
    )
    refreshed = {
        "project_type": "translation",
        "order_no": "TP-260812-010",
        "client_short_name": "客户",
        "manager_contact": None,
        "project_name": "客户-260812",
        "customer_order_no": None,
        "subject_prefix": None,
        "subject_parts": ["TP-260812-010", "客户", "客户-260812"],
        "email_subject_preview": "TP-260812-010，客户，客户-260812",
        "missing_fields": ["负责人联系方式"],
    }
    monkeypatch.setattr(
        "routers.consultations._confirmation_preview_values",
        lambda _db, _payload: refreshed,
    )

    with pytest.raises(HTTPException) as exc_info:
        _confirm_consultation_project(
            object(),
            consultation,
            ConsultationConfirmationFields(
                expected_order_no="TP-260812-009",
                project_name="客户-260812",
            ),
            uuid4(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["preview"]["order_no"] == "TP-260812-010"
