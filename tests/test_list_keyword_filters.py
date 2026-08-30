"""五个常用列表关键词与高级筛选的查询契约回归测试。"""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from annotation_models import AnnotationProject
from annotation_service import _apply_filters as apply_annotation_filters
from crud import _apply_consultation_filters, _apply_translation_project_filters
from interpretation_models import InterpretationProject
from interpretation_service import _apply_filters as apply_interpretation_filters
from models import Client, Consultation, SubClient, TranslationProject
from recruitment_models import RecruitmentProject
from recruitment_service import _apply_filters as apply_recruitment_filters


USER_ID = UUID("00000000-0000-0000-0000-000000000001")
CLIENT_ID = UUID("00000000-0000-0000-0000-000000000002")
SUB_CLIENT_ID = UUID("00000000-0000-0000-0000-000000000003")
LANGUAGE_ID = UUID("00000000-0000-0000-0000-000000000004")


def _base_query(model):
    return (
        select(model.id)
        .outerjoin(Client, model.client_id == Client.id)
        .outerjoin(SubClient, model.sub_client_id == SubClient.id)
    )


def _sql(statement) -> str:
    return str(statement.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )).lower()


def _assert_keyword_columns(sql: str, table: str, extra_columns=()):
    expected = (
        f"{table}.order_no",
        f"{table}.project_name",
        f"{table}.customer_order_no",
        "client.client_name",
        "client.client_short_name",
        "sub_client.client_name",
        "sub_client.client_short_name",
        *extra_columns,
    )
    for column in expected:
        assert column in sql


def test_consultation_keyword_covers_code_project_customer_order_and_all_client_names():
    sql = _sql(_apply_consultation_filters(
        _base_query(Consultation),
        keyword="唯一关键字",
        status="pending",
        consultation_date_start=date(2026, 8, 1),
        consultation_date_end=date(2026, 8, 31),
    ))
    for column in (
        "consultation.consultation_code",
        "consultation.project_name",
        "consultation.customer_order_no",
        "client.client_name",
        "client.client_short_name",
        "sub_client.client_name",
        "sub_client.client_short_name",
    ):
        assert column in sql
    assert "consultation.status" in sql
    assert "consultation.consultation_time" in sql


def test_translation_keyword_and_advanced_filters_share_one_and_query():
    sql = _sql(_apply_translation_project_filters(
        _base_query(TranslationProject),
        keyword="唯一关键字",
        project_status="confirmed",
        task_type="笔译项目",
        service_content="翻译",
        priority="紧急",
        project_manager_id=USER_ID,
        customer_deadline_date_start=date(2026, 8, 1),
        customer_deadline_date_end=date(2026, 8, 31),
        created_date_start=date(2026, 7, 1),
        created_date_end=date(2026, 8, 31),
    ))
    _assert_keyword_columns(sql, "translation_project")
    for column in (
        "translation_project.project_status",
        "translation_project.task_type",
        "translation_project.service_content",
        "translation_project.priority",
        "translation_project.project_manager_id",
        "translation_project.customer_deadline_time",
        "translation_project.created_at",
    ):
        assert column in sql


def test_interpretation_keyword_preserves_task_description_and_new_exact_filters():
    sql = _sql(apply_interpretation_filters(
        _base_query(InterpretationProject),
        keyword="唯一关键字",
        project_status="in_progress",
        client_id=CLIENT_ID,
        sub_client_id=SUB_CLIENT_ID,
        language_id=LANGUAGE_ID,
    ))
    _assert_keyword_columns(sql, "interpretation_project", ("interpretation_project.task_description",))
    assert "interpretation_project.client_id" in sql
    assert "interpretation_project.sub_client_id" in sql
    assert "interpretation_project_language_direction.source_language_id" in sql
    assert "interpretation_project_language_direction.target_language_id" in sql


def test_annotation_keyword_preserves_task_and_contact_fields_with_advanced_and():
    sql = _sql(apply_annotation_filters(
        _base_query(AnnotationProject),
        keyword="唯一关键字",
        project_status="project_in_progress",
        client_manager_id=USER_ID,
        client_id=CLIENT_ID,
        created_date_start=date(2026, 8, 1),
        created_date_end=date(2026, 8, 31),
    ))
    _assert_keyword_columns(sql, "annotation_project", (
        "annotation_project.task_description",
        "annotation_project.contact_name",
    ))
    assert "annotation_project.client_manager_id" in sql
    assert "annotation_project.created_at" in sql


def test_recruitment_keyword_preserves_position_description_and_location_fields():
    sql = _sql(apply_recruitment_filters(
        _base_query(RecruitmentProject),
        keyword="唯一关键字",
        project_status="sourcing",
        client_manager_id=USER_ID,
        client_id=CLIENT_ID,
        created_date_start=date(2026, 8, 1),
        created_date_end=date(2026, 8, 31),
    ))
    _assert_keyword_columns(sql, "recruitment_project", (
        "recruitment_project.position_title",
        "recruitment_project.job_description",
        "recruitment_project.work_location",
    ))
    assert "recruitment_project.client_manager_id" in sql
    assert "recruitment_project.created_at" in sql
