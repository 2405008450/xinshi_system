from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from concurrency import StaleUpdateError
from inline_text_update import (
    TextFieldRule,
    TextFieldUpdate,
    apply_text_field_update,
    normalize_text_value,
)
from routers.annotation_projects import ANNOTATION_TEXT_FIELDS
from routers.consultations import (
    CONSULTATION_INTAKE_TEXT_FIELDS,
    CONSULTATION_TEXT_FIELDS,
)
from routers.interpretation_projects import INTERPRETATION_TEXT_FIELDS
from routers.recruitment_projects import RECRUITMENT_TEXT_FIELDS
from routers.resource_requests import RESOURCE_REQUEST_TEXT_FIELDS
from routers.translation_projects import TRANSLATION_TEXT_FIELDS


def test_text_field_whitelists_match_detail_quick_edit_scope():
    assert set(CONSULTATION_TEXT_FIELDS) == {
        "client_source", "source_keyword", "consultation_description",
        "project_name", "customer_order_no", "contact_name",
        "handling_method", "follow_up_status", "follow_up_remarks", "remarks",
    }
    assert set(TRANSLATION_TEXT_FIELDS) == {
        "project_name", "email_subject_preview", "task_type", "service_content",
        "customer_order_no", "file_type_secondary", "project_contract_type",
        "project_contract_status", "quotation_status", "quotation_path",
        "customer_requirement_professional", "customer_requirement_special",
        "client_feedback",
    }
    assert set(INTERPRETATION_TEXT_FIELDS) == {
        "project_name", "task_description", "customer_budget", "contact_name",
        "customer_order_no", "interpreter_special_requirements",
        "interpreter_height_requirement", "interpreter_appearance_requirement",
        "interpreter_dress_requirement", "interpretation_domain",
        "interpretation_content", "file_path", "quotation_path", "contract_path",
        "client_rating_note", "social_post_request", "resource_request", "remarks",
        "email_subject_preview",
    }
    assert set(ANNOTATION_TEXT_FIELDS) == {
        "language_region", "project_name", "task_description", "potential_demand",
        "contact_name", "customer_order_no", "email_subject_preview",
        "project_path", "quotation_path", "contract_path",
    }
    assert set(RECRUITMENT_TEXT_FIELDS) == {
        "project_name", "job_description", "position_title", "contact_name",
        "customer_order_no", "work_location", "service_fee_note", "project_path",
        "quotation_path", "contract_path", "remarks", "email_subject_preview",
        "social_post_request", "resource_request",
    }
    assert set(RESOURCE_REQUEST_TEXT_FIELDS) == {"request_detail"}


def test_consultation_intake_whitelists_are_isolated_by_project_type():
    assert set(CONSULTATION_INTAKE_TEXT_FIELDS) == {
        "translation", "interpretation", "annotation", "recruitment",
    }
    assert "service_content" in CONSULTATION_INTAKE_TEXT_FIELDS["translation"]
    assert set(CONSULTATION_INTAKE_TEXT_FIELDS["interpretation"]) == {"task_description"}
    assert set(CONSULTATION_INTAKE_TEXT_FIELDS["annotation"]) == {
        "task_description", "potential_demand",
    }
    assert set(CONSULTATION_INTAKE_TEXT_FIELDS["recruitment"]) == {
        "position_title", "job_description", "work_location",
    }


@pytest.mark.parametrize(
    ("value", "rule", "expected"),
    [
        ("  新名称  ", TextFieldRule(max_length=20), "新名称"),
        ("   ", TextFieldRule(), None),
        ("   ", TextFieldRule(empty_as_null=False), ""),
        ("普通路径", TextFieldRule(managed_path=True), "普通路径"),
    ],
)
def test_normalize_text_value(value, rule, expected):
    assert normalize_text_value(value, rule) == expected


def test_required_and_length_rules_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_text_value("  ", TextFieldRule(required=True))
    with pytest.raises(ValueError):
        normalize_text_value("1234", TextFieldRule(max_length=3))


def test_apply_text_field_update_only_changes_whitelisted_target():
    version = datetime.now()
    row = SimpleNamespace(project_name="旧名称", remarks="保留", updated_at=version)
    changed = apply_text_field_update(
        row,
        TextFieldUpdate(
            field="project_name",
            value="  新名称 ",
            expected_updated_at=version,
        ),
        {"project_name": TextFieldRule(max_length=20)},
    )
    assert changed is True
    assert row.project_name == "新名称"
    assert row.remarks == "保留"
    assert row.updated_at > version


def test_apply_text_field_update_rejects_unknown_field_and_stale_version():
    version = datetime.now()
    row = SimpleNamespace(project_name="名称", updated_at=version)
    with pytest.raises(ValueError):
        apply_text_field_update(
            row,
            TextFieldUpdate(field="project_status", value="cancelled"),
            {"project_name": TextFieldRule()},
        )
    with pytest.raises(StaleUpdateError):
        apply_text_field_update(
            row,
            TextFieldUpdate(
                field="project_name",
                value="新名称",
                expected_updated_at=version - timedelta(seconds=1),
            ),
            {"project_name": TextFieldRule()},
        )


def test_no_change_does_not_refresh_version():
    version = datetime.now()
    row = SimpleNamespace(project_name="名称", updated_at=version)
    changed = apply_text_field_update(
        row,
        TextFieldUpdate(field="project_name", value=" 名称 ", expected_updated_at=version),
        {"project_name": TextFieldRule()},
    )
    assert changed is False
    assert row.updated_at == version
