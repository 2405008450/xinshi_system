from datetime import datetime
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
    _confirmation_project_type,
    _confirmation_preview_values,
    _remove_customer_identifier_requirement,
    consultation_task_type_label,
    validate_consultation_required_fields,
    validate_simple_consultation,
)
from schemas import ConsultationCreate, TranslationProjectCreate


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
    assert missing == ["客户经理联系方式"]


def test_interpretation_subject_contains_customer_identifier():
    parts, subject, missing = _build_subject_preview(
        project_type="interpretation",
        subject_prefix=None,
        order_no="IP-260812-001",
        client_short_name="信实客户",
        manager_contact="张经理 13800000000",
        customer_order_no="PO-88",
        project_name="信实客户-260812",
    )

    assert parts[-2:] == ["PO-88", "信实客户-260812"]
    assert subject == "IP-260812-001，信实客户，张经理 13800000000，PO-88，信实客户-260812"
    assert missing == []


def test_customer_identifier_is_optional_in_confirmation_preview():
    parts, subject, missing = _build_subject_preview(
        project_type="interpretation",
        subject_prefix=None,
        order_no="IP-260812-002",
        client_short_name="信实客户",
        manager_contact="张经理 13800000000",
        customer_order_no=None,
        project_name="信实客户-260812",
    )

    assert parts == ["IP-260812-002", "信实客户", "张经理 13800000000", "信实客户-260812"]
    assert "客户单号/标识" not in missing
    assert subject == "IP-260812-002，信实客户，张经理 13800000000，信实客户-260812"


def test_legacy_customer_identifier_blocker_is_removed_without_hiding_other_errors():
    preview = _remove_customer_identifier_requirement({
        "missing_fields": ["客户单号/标识", "服务内容"],
        "blocking_reasons": [
            "请先填写核心字段：客户单号/项目标识、服务内容",
            "默认邮件组中没有可用用户",
        ],
        "can_send": False,
    })

    assert preview["missing_fields"] == ["服务内容"]
    assert preview["blocking_reasons"] == [
        "请先填写核心字段：服务内容",
        "默认邮件组中没有可用用户",
    ]
    assert preview["can_send"] is False

    customer_identifier_only = _remove_customer_identifier_requirement({
        "missing_fields": ["客户单号/标识"],
        "blocking_reasons": ["请先填写核心字段：客户单号/标识"],
        "can_send": False,
    })
    assert customer_identifier_only["missing_fields"] == []
    assert customer_identifier_only["blocking_reasons"] == []
    assert customer_identifier_only["can_send"] is True


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


@pytest.mark.parametrize(
    ("consultation_type", "task_type"),
    [
        ("配音项目", "配音项目"),
        ("字幕项目", "字幕项目"),
        ("公证项目", "公证项目"),
        ("认证项目", "认证项目"),
        ("其他项目", "其他项目"),
    ],
)
def test_translation_family_types_use_translation_confirmation_and_keep_task_type(
    consultation_type, task_type
):
    assert _confirmation_project_type(consultation_type) == "translation"
    assert consultation_task_type_label(consultation_type) == task_type


def test_simple_consultation_requires_minimum_fields_and_rejects_confirmation():
    valid = ConsultationCreate(
        client_short_name="测试客户",
        consultation_time=datetime(2026, 8, 31, 10, 30),
        consultation_method="phone",
        client_source="电话来访",
        consultation_description="测试咨询需求",
        consultation_type="简单咨询",
        status="following",
    )
    validate_simple_consultation(valid)

    with pytest.raises(ValueError, match="客户来源"):
        validate_simple_consultation(valid.model_copy(update={"client_source": ""}))

    with pytest.raises(ValueError, match="不能直接设为已确认"):
        validate_simple_consultation(valid.model_copy(update={"status": "success"}))

    with pytest.raises(ValueError, match="不能直接确认建项"):
        _confirmation_project_type("简单咨询")


@pytest.mark.parametrize("consultation_type", ["口译项目", "招聘项目", "标注项目"])
def test_project_consultation_requires_front_loaded_core_fields(consultation_type):
    valid = ConsultationCreate(
        client_short_name="测试客户",
        consultation_time=datetime(2026, 8, 31, 10, 30),
        consultation_method="phone",
        client_source="电话来访",
        source_keyword="老客户推荐",
        consultation_description="测试咨询需求",
        consultation_type=consultation_type,
        status="following",
    )
    validate_consultation_required_fields(valid)

    with pytest.raises(ValueError, match="来源关键词、咨询描述"):
        validate_consultation_required_fields(
            valid.model_copy(update={"source_keyword": "", "consultation_description": ""})
        )


@pytest.mark.parametrize("consultation_type", ["简单咨询", "笔译项目", "口译项目", "其他项目"])
def test_all_consultation_types_require_source_and_description(consultation_type):
    payload = ConsultationCreate(
        client_short_name="测试客户",
        consultation_time=datetime(2026, 8, 31, 10, 30),
        consultation_method="phone",
        client_source="未知",
        source_keyword="无",
        consultation_description="无",
        consultation_type=consultation_type,
        status="following",
    )
    validate_consultation_required_fields(payload)

    with pytest.raises(ValueError, match="客户来源、咨询描述"):
        validate_consultation_required_fields(
            payload.model_copy(update={"client_source": "", "consultation_description": ""})
        )


def test_consultation_method_is_required_and_supports_optional_detail():
    payload = ConsultationCreate(
        client_short_name="测试客户",
        consultation_method="phone",
        consultation_method_detail="总机 021-12345678，张经理 13800000000",
        client_source="未知",
        consultation_description="无",
        consultation_type="笔译项目",
        status="following",
    )
    validate_consultation_required_fields(payload)
    assert payload.consultation_method_detail.startswith("总机")

    with pytest.raises(ValueError, match="咨询方式"):
        validate_consultation_required_fields(payload.model_copy(update={"consultation_method": ""}))

    with pytest.raises(ValueError, match="具体咨询方式"):
        validate_consultation_required_fields(
            payload.model_copy(update={"consultation_method": "other", "consultation_method_detail": ""})
        )


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
        "missing_fields": ["客户经理联系方式"],
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
