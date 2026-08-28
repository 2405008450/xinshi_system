"""咨询售前数据校验及确认建项时的一次性映射。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from annotation_models import AnnotationProjectAssignee, AnnotationProjectLanguageItem, AnnotationProjectPriceItem
from annotation_schemas import AnnotationProjectUpdate
from annotation_service import _sync_nested as sync_annotation_nested
from interpretation_models import InterpretationProjectInterpreter, InterpretationProjectLanguageDirection, InterpretationProjectTimeRange
from interpretation_schemas import InterpretationProjectUpdate
from interpretation_service import _sync_nested as sync_interpretation_nested
from models import TranslationProject
from recruitment_schemas import RecruitmentProjectUpdate
from recruitment_service import _sync_languages as sync_recruitment_languages
from word_count_schemas import WordCountCreateMatrix
from word_count_service import save_created_entity_matrix


SCALAR_FIELDS = {
    "translation": (
        "service_content", "file_type_secondary", "language_pair", "customer_deadline_time",
        "priority", "project_contract_type", "project_contract_status", "quotation_required",
        "quotation_status", "quotation_path", "customer_requirement_professional",
        "customer_requirement_special",
    ),
    "interpretation": (
        "project_types", "task_description", "locations", "customer_budget",
        "required_interpreter_count", "required_interpreter_gender", "required_interpretation_level",
        "interpreter_special_requirements", "interpreter_height_requirement",
        "interpreter_appearance_requirement", "interpreter_dress_requirement",
        "interpretation_domain", "interpretation_content", "file_path", "quotation_path",
        "contract_path", "social_post_request", "resource_request", "remarks",
    ),
    "annotation": (
        "project_types", "task_description", "potential_demand", "project_path",
        "quotation_path", "contract_path",
    ),
    "recruitment": (
        "job_description", "position_title", "headcount_min", "headcount_max",
        "target_onboard_type", "target_onboard_date", "employment_start", "employment_end",
        "work_location", "service_fee_type", "service_fee_currency", "service_fee_amount",
        "service_fee_rate", "service_fee_note", "project_path", "quotation_path", "contract_path",
        "social_post_request", "resource_request", "remarks",
    ),
}


def validated_intake(project_type: str, intake: Optional[dict]) -> dict:
    data = dict(intake or {})
    # JSONB 与邮件预览都需要可 json.dumps 的结构；mode="json" 会把 date/datetime/UUID 转成字符串。
    if project_type == "interpretation":
        return InterpretationProjectUpdate(**data).model_dump(mode="json", exclude={"interpreter_assignments", "expected_updated_at"})
    if project_type == "annotation":
        return AnnotationProjectUpdate(**data).model_dump(mode="json", exclude={"assignees", "expected_updated_at"})
    if project_type == "recruitment":
        return RecruitmentProjectUpdate(**data).model_dump(mode="json", exclude={"expected_updated_at"})
    if project_type == "translation":
        if "word_count_matrix" in data:
            data["word_count_matrix"] = WordCountCreateMatrix.model_validate(data["word_count_matrix"]).model_dump(mode="json")
        return {key: value for key, value in data.items() if key in {*SCALAR_FIELDS[project_type], "word_count_matrix"}}
    raise ValueError("不支持的项目类型")


def apply_intake(
    db: Session,
    *,
    project_type: str,
    project,
    intake: Optional[dict],
    sub_client_id: Optional[UUID],
    contact_name: Optional[str],
    customer_order_no: Optional[str],
    updated_by: Optional[UUID],
) -> None:
    data = validated_intake(project_type, intake)
    if hasattr(project, "sub_client_id"):
        project.sub_client_id = sub_client_id
    if hasattr(project, "contact_name"):
        project.contact_name = contact_name
    if hasattr(project, "customer_order_no"):
        project.customer_order_no = customer_order_no
    for field in SCALAR_FIELDS[project_type]:
        if field in data:
            setattr(project, field, data[field])

    if project_type == "translation" and "word_count_matrix" in data:
        save_created_entity_matrix(
            db, "project", project.id,
            WordCountCreateMatrix.model_validate(data["word_count_matrix"]),
            updated_by=updated_by,
        )
    elif project_type == "interpretation":
        payload = InterpretationProjectUpdate(**data)
        payload.interpreter_assignments = []
        sync_interpretation_nested(db, project, payload)
    elif project_type == "annotation":
        payload = AnnotationProjectUpdate(**data)
        payload.assignees = []
        sync_annotation_nested(db, project, payload)
    elif project_type == "recruitment":
        sync_recruitment_languages(db, project, RecruitmentProjectUpdate(**data))
    if hasattr(project, "updated_at"):
        project.updated_at = datetime.now()
    db.flush()
