import json

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import CompileError
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from annotation_models import AnnotationProject
from annotation_service import _apply_filters as apply_annotation_filters
from crud import _apply_client_filters, _apply_translation_project_filters
from field_filtering import parse_field_filters
from interpretation_models import InterpretationProject
from interpretation_service import _apply_filters as apply_interpretation_filters
from models import Client, SubClient, TranslationProject
from recruitment_models import RecruitmentProject
from recruitment_service import _apply_filters as apply_recruitment_filters
from resource_service import _talent_query
from resource_request_service import _view_filter_sql
from routers.clients import _field_filters as client_field_filters
from routers.interpretation_projects import _field_filters as interpretation_field_filters
from routers.recruitment_projects import _field_filters as recruitment_field_filters
from routers.resource_requests import _field_filters as request_field_filters
from routers.talents import _field_filters as talent_field_filters
from routers.translation_projects import _field_filters as translation_field_filters


def encoded(value):
    return json.dumps(value, ensure_ascii=False)


def compiled_sql(statement):
    if hasattr(statement, "statement"):
        statement = statement.statement
    try:
        return str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})).lower()
    except CompileError:
        return str(statement.compile(dialect=postgresql.dialect())).lower()


def project_query(model):
    return select(model.id).outerjoin(Client, model.client_id == Client.id).outerjoin(SubClient, model.sub_client_id == SubClient.id)


@pytest.mark.parametrize(
    ("parser", "payload"),
    [
        (client_field_filters, {"client_name": {"op": "contains", "value": "信实"}}),
        (translation_field_filters, {"project_status": {"op": "in", "value": ["confirmed", "paused"]}}),
        (interpretation_field_filters, {"scheduled_date": {"op": "between", "from": "2026-08-01", "to": "2026-08-31"}}),
        (recruitment_field_filters, {"candidate_count": {"op": "between", "min": 1, "max": 5}}),
        (talent_field_filters, {"duplicate_review_required": {"op": "eq", "value": True}}),
        (request_field_filters, {"languages": {"op": "in", "value": ["00000000-0000-0000-0000-000000000001"]}}),
        (request_field_filters, {"demand_status": {"op": "in", "value": ["confirmed", "cancelled"]}}),
    ],
)
def test_module_field_filter_contract_accepts_supported_shapes(parser, payload):
    assert parser(encoded(payload)) == payload


@pytest.mark.parametrize(
    ("parser", "payload"),
    [
        (client_field_filters, {"unknown": {"op": "contains", "value": "x"}}),
        (translation_field_filters, {"word_count": {"op": "contains", "value": "10"}}),
        (interpretation_field_filters, {"translator_id": {"op": "contains", "value": "x"}}),
        (recruitment_field_filters, {"candidate_count": {"op": "eq", "value": 2}}),
        (talent_field_filters, {"status": {"op": "contains", "value": "active"}}),
        (request_field_filters, {"requested_at": {"op": "eq", "value": "2026-08-30"}}),
    ],
)
def test_module_field_filter_contract_rejects_unknown_fields_and_wrong_operators(parser, payload):
    with pytest.raises(HTTPException) as exc_info:
        parser(encoded(payload))
    assert exc_info.value.status_code == 422


def test_parse_field_filters_rejects_malformed_json_and_empty_in_values():
    with pytest.raises(HTTPException) as malformed:
        parse_field_filters("{")
    assert malformed.value.status_code == 422

    with pytest.raises(HTTPException) as empty_values:
        parse_field_filters(encoded({"status": {"op": "in", "value": []}}))
    assert empty_values.value.status_code == 422


def test_resource_request_sql_uses_and_between_fields_and_or_inside_multi_select():
    sql, params = _view_filter_sql(field_filters={
        "project_status": {"op": "in", "value": ["in_progress", "closed"]},
        "languages": {"op": "in", "value": ["lang-a", "lang-b"]},
        "required_count": {"op": "between", "min": 2, "max": 4},
    })

    assert "current_project_status IN" in sql
    assert "EXISTS (SELECT 1 FROM resource_request_item" in sql
    assert " OR " in sql
    assert "item.required_count >=" in sql and "item.required_count <=" in sql
    assert set(params.values()) >= {"in_progress", "closed", "lang-a", "lang-b", 2, 4}


def test_project_field_filters_compile_relations_aggregates_and_cross_field_and():
    translation_sql = compiled_sql(_apply_translation_project_filters(
        project_query(TranslationProject),
        field_filters={
            "project_status": {"op": "in", "value": ["confirmed", "paused"]},
            "translator_name": {"op": "contains", "value": "张"},
            "word_count": {"op": "between", "min": 1000, "max": 5000},
        },
    ))
    assert "translation_project.project_status in" in translation_sql
    assert "translation_sub_order.status in" in translation_sql
    assert "translator.translator_name" in translation_sql
    assert "manuscript_arrangement.translator_name_snapshot" in translation_sql
    assert "word_count_metric" in translation_sql

    interpretation_sql = compiled_sql(apply_interpretation_filters(
        project_query(InterpretationProject),
        field_filters={
            "project_types": {"op": "in", "value": ["onsite", "booth"]},
            "required_interpreter_count": {"op": "between", "min": 1, "max": 3},
        },
    ))
    assert "interpretation_project.project_types" in interpretation_sql
    assert "required_interpreter_count >=" in interpretation_sql
    assert " or " in interpretation_sql

    annotation_sql = compiled_sql(apply_annotation_filters(
        project_query(AnnotationProject),
        field_filters={
            "has_customer_price": {"op": "eq", "value": True},
            "customer_price": {"op": "between", "min": 0.1, "max": 2.5},
        },
    ))
    assert "annotation_project_price_item" in annotation_sql
    assert "annotation_project_price_item.amount >=" in annotation_sql

    recruitment_sql = compiled_sql(apply_recruitment_filters(
        project_query(RecruitmentProject),
        field_filters={
            "headcount": {"op": "between", "min": 2, "max": 8},
            "candidate_count": {"op": "between", "min": 1, "max": 10},
        },
    ))
    assert "headcount_max >=" in recruitment_sql and "headcount_min <=" in recruitment_sql
    assert "count(recruitment_candidate.id)" in recruitment_sql


def test_client_and_talent_field_filters_compile_to_related_record_predicates():
    client_sql = compiled_sql(_apply_client_filters(
        select(Client.id),
        field_filters={
            "client_name": {"op": "contains", "value": "科技"},
            "client_status": {"op": "in", "value": ["active", "pending"]},
        },
    ))
    assert "client.client_name" in client_sql
    assert "sub_client.client_name" in client_sql
    assert "client.client_status in" in client_sql

    talent_sql = compiled_sql(_talent_query(Session(), field_filters={
        "capability_types": {"op": "in", "value": ["written_translation", "interpretation"]},
        "years_experience": {"op": "between", "min": 3, "max": 10},
        "duplicate_review_required": {"op": "eq", "value": False},
    }))
    assert "resource_capability.capability_type in" in talent_sql
    assert "resource_career_profile.years_experience >=" in talent_sql
    assert "duplicate_review_required = false" in talent_sql
