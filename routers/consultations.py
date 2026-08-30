from typing import List, Optional
from uuid import uuid4
from uuid import UUID
from datetime import date, datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from crud import (
    count_consultations, get_consultation, get_consultations,
    create_consultation, update_consultation, delete_consultation,
    build_auto_project_name, create_translation_project, get_translation_projects
)
from schemas import ConsultationCreate, ConsultationUpdate, ConsultationResponse, TranslationProjectCreate, TranslationProjectResponse
from models import AppUser, Client, Consultation, TranslationProject
from utils import generate_order_no
from interpretation_models import InterpretationProject
from interpretation_service import (
    ensure_interpretation_project_for_consultation,
    generate_interpretation_order_no,
    is_interpretation_type,
    validate_consultation_project_type_change,
)
from annotation_models import AnnotationProject
from annotation_service import (
    ensure_annotation_project_for_consultation,
    generate_annotation_order_no,
    is_annotation_type,
    is_translation_type,
    validate_consultation_annotation_type_change,
)
from recruitment_models import RecruitmentProject
from recruitment_service import (
    ensure_recruitment_project_for_consultation,
    generate_recruitment_order_no,
    is_recruitment_type,
    validate_consultation_recruitment_type_change,
)
from routers.auth import get_current_user, require_any_permission, require_module_access
from business_mail_schemas import BusinessMailSendRequest
from business_mail_service import (
    build_preview as build_mail_preview,
    create_and_send,
    serialize_mail,
    validate_internal_users,
)
from consultation_intake import apply_intake, validated_intake
from concurrency import assert_fresh
from inline_text_update import (
    TextFieldRule,
    TextFieldUpdate,
    apply_text_field_update,
    normalize_text_value,
)

router = APIRouter(prefix="/consultations", tags=["consultations"], dependencies=[Depends(require_module_access("consultations:read", "consultations:write"))])


CONSULTATION_TEXT_FIELDS = {
    "client_source": TextFieldRule(max_length=100),
    "source_keyword": TextFieldRule(max_length=255),
    "consultation_description": TextFieldRule(),
    "project_name": TextFieldRule(max_length=500),
    "customer_order_no": TextFieldRule(max_length=150),
    "contact_name": TextFieldRule(max_length=255),
    "handling_method": TextFieldRule(max_length=100),
    "follow_up_status": TextFieldRule(max_length=20),
    "follow_up_remarks": TextFieldRule(),
    "remarks": TextFieldRule(),
}

CONSULTATION_INTAKE_TEXT_FIELDS = {
    "translation": {
        "service_content": TextFieldRule(max_length=255),
        "file_type_secondary": TextFieldRule(max_length=100),
        "project_contract_type": TextFieldRule(max_length=100),
        "project_contract_status": TextFieldRule(max_length=100),
        "quotation_status": TextFieldRule(max_length=100),
        "quotation_path": TextFieldRule(managed_path=True),
        "customer_requirement_professional": TextFieldRule(),
        "customer_requirement_special": TextFieldRule(),
    },
    "interpretation": {
        "task_description": TextFieldRule(),
    },
    "annotation": {
        "task_description": TextFieldRule(required=True),
        "potential_demand": TextFieldRule(),
    },
    "recruitment": {
        "position_title": TextFieldRule(max_length=255, required=True),
        "job_description": TextFieldRule(),
        "work_location": TextFieldRule(max_length=500, required=True),
    },
}


class CreateProjectFromConsultationRequest(BaseModel):
    project_name: Optional[str] = None


class ConsultationConfirmationFields(BaseModel):
    project_name: Optional[str] = Field(default=None, max_length=255)
    expected_order_no: str = Field(min_length=1, max_length=50)
    subject_prefix: Optional[str] = Field(default=None, max_length=50)
    customer_order_no: Optional[str] = Field(default=None, max_length=150)
    project_intake: dict = Field(default_factory=dict)
    to_user_ids: List[UUID] = Field(default_factory=list)
    cc_user_ids: List[UUID] = Field(default_factory=list)
    email_subject: Optional[str] = Field(default=None, max_length=1000)
    email_body: Optional[str] = Field(default=None, max_length=50000)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=100)


class ConsultationConfirmationPreviewRequest(BaseModel):
    consultation_id: Optional[UUID] = None
    consultation_type: str = Field(min_length=1, max_length=50)
    client_id: Optional[UUID] = None
    client_short_name: Optional[str] = Field(default=None, max_length=100)
    manager_contact: Optional[str] = Field(default=None, max_length=100)
    project_name: Optional[str] = Field(default=None, max_length=255)
    subject_prefix: Optional[str] = Field(default=None, max_length=50)
    customer_order_no: Optional[str] = Field(default=None, max_length=150)
    project_intake: dict = Field(default_factory=dict)
    consultation_description: Optional[str] = None
    remarks: Optional[str] = None


class CreateConfirmedConsultationRequest(BaseModel):
    consultation: ConsultationCreate
    confirmation: ConsultationConfirmationFields


class UpdateConfirmedConsultationRequest(BaseModel):
    consultation: Optional[ConsultationUpdate] = None
    confirmation: ConsultationConfirmationFields


class ConsultationConfirmationPreviewResponse(BaseModel):
    project_type: str
    order_no: str
    client_short_name: Optional[str] = None
    manager_contact: Optional[str] = None
    project_name: str
    customer_order_no: Optional[str] = None
    subject_prefix: Optional[str] = None
    subject_parts: List[str]
    email_subject_preview: str
    missing_fields: List[str]
    to_users: list[dict] = Field(default_factory=list)
    cc_users: list[dict] = Field(default_factory=list)
    email_body: str = ""
    sender_mode: str = "system"
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    sender_verified: bool = False
    can_send: bool = False
    blocking_reasons: List[str] = Field(default_factory=list)


class ConsultationConfirmationResponse(BaseModel):
    consultation: ConsultationResponse
    project_type: str
    project_id: UUID
    order_no: str
    email_subject_preview: str
    mail: Optional[dict] = None


CONSULTATION_CONFIRMED_STATUS = "success"
PROJECT_CONFIRMED_STATUS = "confirmed"


CONSULTATION_TASK_TYPE_LABELS = {
    "translation": "笔译项目",
    "interpretation": "口译项目",
    "recruitment": "招聘项目",
    "annotation": "标注项目",
    "dubbing": "配音项目",
    "subtitle": "字幕项目",
    "notarization": "公证项目",
    "certification": "认证项目",
    "equipment_rental": "其他项目",
    "other": "其他项目",
    "笔译": "笔译项目",
    "口译": "口译项目",
    "招聘": "招聘项目",
    "其他": "其他项目",
}


def _confirmation_project_type(value: Optional[str]) -> str:
    if is_interpretation_type(value):
        return "interpretation"
    if is_translation_type(value):
        return "translation"
    if is_annotation_type(value):
        return "annotation"
    if is_recruitment_type(value):
        return "recruitment"
    raise ValueError("只有笔译、口译、标注和招聘项目使用项目确认预览")


def _clean_text(value: Optional[str]) -> str:
    return (value or "").strip()


def _build_subject_preview(
    *,
    project_type: str,
    subject_prefix: Optional[str],
    order_no: str,
    client_short_name: Optional[str],
    manager_contact: Optional[str],
    customer_order_no: Optional[str],
    project_name: Optional[str],
) -> tuple[list[str], str, list[str]]:
    values = [
        ("标题前缀", subject_prefix),
        ("订单号", order_no),
        ("客户简称", client_short_name),
        ("负责人联系方式", manager_contact),
    ]
    if project_type != "translation":
        values.append(("客户单号/标识", customer_order_no))
    values.append(("项目名称", project_name))
    parts = [_clean_text(value) for _label, value in values if _clean_text(value)]
    missing = [
        label for label, value in values
        if label != "标题前缀" and not _clean_text(value)
    ]
    return parts, "，".join(parts), missing


def _confirmation_preview_values(
    db: Session,
    payload: ConsultationConfirmationPreviewRequest,
    current_user: Optional[AppUser] = None,
) -> dict:
    consultation = None
    if payload.consultation_id:
        consultation = get_consultation(db, payload.consultation_id)
        if not consultation:
            raise ValueError("咨询记录不存在")

    consultation_type = payload.consultation_type or (
        consultation.consultation_type if consultation else None
    )
    project_type = _confirmation_project_type(consultation_type)
    client_id = payload.client_id or (consultation.client_id if consultation else None)
    client = db.query(Client).filter(Client.id == client_id).first() if client_id else None
    if client:
        client_short_name = client.client_short_name
    elif payload.client_short_name:
        client_short_name = payload.client_short_name
    else:
        client_short_name = getattr(consultation, "client_short_name", None)
    manager_contact = (
        payload.manager_contact
        if "manager_contact" in payload.model_fields_set
        else client.manager_contact if client else None
    )

    existing_project = None
    if consultation:
        project_model = {
            "translation": TranslationProject,
            "interpretation": InterpretationProject,
            "annotation": AnnotationProject,
            "recruitment": RecruitmentProject,
        }[project_type]
        existing_project = db.query(project_model).filter(
            project_model.consultation_id == consultation.id
        ).first()

    order_no = (
        existing_project.order_no if existing_project else
        generate_interpretation_order_no(db) if project_type == "interpretation" else
        generate_annotation_order_no(db) if project_type == "annotation" else
        generate_recruitment_order_no(db) if project_type == "recruitment" else
        generate_order_no(db)
    )
    project_name = _clean_text(payload.project_name) or _clean_text(
        getattr(existing_project, "project_name", None)
    ) or build_auto_project_name(client_short_name)
    customer_order_no = (
        _clean_text(payload.customer_order_no)
        if project_type != "translation"
        else ""
    )
    if project_type != "translation" and not customer_order_no:
        customer_order_no = _clean_text(getattr(existing_project, "customer_order_no", None))

    parts, subject, missing = _build_subject_preview(
        project_type=project_type,
        subject_prefix=payload.subject_prefix,
        order_no=order_no,
        client_short_name=client_short_name,
        manager_contact=manager_contact,
        customer_order_no=customer_order_no,
        project_name=project_name,
    )
    source = {
        **validated_intake(project_type, payload.project_intake),
        "order_no": order_no,
        "project_name": project_name,
        "client_short_name": client_short_name,
        "manager_contact": manager_contact,
        "customer_order_no": customer_order_no,
        "subject_prefix": payload.subject_prefix,
        "consultation_description": payload.consultation_description,
        "remarks": payload.remarks,
    }
    # 正式接口始终传入 SQLAlchemy Session；保留轻量级纯函数回退，便于主题生成单元测试。
    if isinstance(db, Session):
        mail_preview = build_mail_preview(
            db,
            project_type,
            source=source,
            current_user=current_user,
        )
    else:
        mail_preview = {
            "subject": subject,
            "body": "",
            "missing_fields": missing,
            "to_users": [],
            "cc_users": [],
            "can_send": False,
            "blocking_reasons": [],
            "sender_mode": "system",
            "sender_name": None,
            "sender_email": None,
            "sender_verified": False,
        }
    return {
        "project_type": project_type,
        "order_no": order_no,
        "client_short_name": _clean_text(client_short_name) or None,
        "manager_contact": _clean_text(manager_contact) or None,
        "project_name": project_name,
        "customer_order_no": customer_order_no or None,
        "subject_prefix": _clean_text(payload.subject_prefix) or None,
        "subject_parts": parts,
        "email_subject_preview": mail_preview["subject"] or subject,
        "missing_fields": mail_preview["missing_fields"] or missing,
        "to_users": mail_preview["to_users"],
        "cc_users": mail_preview["cc_users"],
        "email_body": mail_preview["body"],
        "sender_mode": mail_preview["sender_mode"],
        "sender_name": mail_preview["sender_name"],
        "sender_email": mail_preview["sender_email"],
        "sender_verified": mail_preview["sender_verified"],
        "can_send": mail_preview["can_send"],
        "blocking_reasons": mail_preview["blocking_reasons"],
    }


def _confirm_consultation_project(
    db: Session,
    consultation,
    confirmation: ConsultationConfirmationFields,
    created_by: UUID,
    current_user: Optional[AppUser] = None,
):
    confirmation_project_type = _confirmation_project_type(consultation.consultation_type)
    next_project_name = _clean_text(confirmation.project_name) or getattr(consultation, "project_name", None)
    next_customer_order_no = _clean_text(confirmation.customer_order_no) or getattr(consultation, "customer_order_no", None)
    next_project_intake = (
        validated_intake(confirmation_project_type, confirmation.project_intake)
        if confirmation.project_intake
        else (
            validated_intake(confirmation_project_type, getattr(consultation, "project_intake", None) or {})
            if confirmation_project_type == "interpretation"
            else (getattr(consultation, "project_intake", None) or {})
        )
    )
    preview_request = ConsultationConfirmationPreviewRequest(
        consultation_id=consultation.id,
        consultation_type=consultation.consultation_type,
        client_id=consultation.client_id,
        client_short_name=getattr(consultation, "client_short_name", None),
        project_name=next_project_name,
        subject_prefix=confirmation.subject_prefix,
        customer_order_no=next_customer_order_no,
        project_intake=next_project_intake,
        consultation_description=getattr(consultation, "consultation_description", None),
        remarks=getattr(consultation, "remarks", None),
    )
    preview = (
        _confirmation_preview_values(db, preview_request, current_user)
        if current_user is not None
        else _confirmation_preview_values(db, preview_request)
    )
    if confirmation.to_user_ids:
        validate_internal_users(db, confirmation.to_user_ids)
        validate_internal_users(
            db,
            [user_id for user_id in confirmation.cc_user_ids if user_id not in set(confirmation.to_user_ids)],
        )
    if confirmation.to_user_ids and not preview.get("can_send", False):
        raise ValueError("；".join(preview.get("blocking_reasons") or ["邮件发送条件不完整"]))
    if preview["project_type"] != "translation":
        # 确认请求中的空值表示用户主动清空，不再回退到项目历史值。
        preview["customer_order_no"] = _clean_text(confirmation.customer_order_no) or None
        parts, subject, missing = _build_subject_preview(
            project_type=preview["project_type"],
            subject_prefix=confirmation.subject_prefix,
            order_no=preview["order_no"],
            client_short_name=preview["client_short_name"],
            manager_contact=preview["manager_contact"],
            customer_order_no=preview["customer_order_no"],
            project_name=preview["project_name"],
        )
        preview.update(
            subject_parts=parts,
            email_subject_preview=subject,
        )
    if preview["order_no"] != confirmation.expected_order_no:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "订单号已被其他项目占用，主题预览已刷新，请重新确认",
                "preview": preview,
            },
        )

    # 只有订单号校验通过后才写回咨询，避免并发冲突留下半成品状态。
    consultation.project_name = next_project_name
    consultation.customer_order_no = next_customer_order_no
    if confirmation.project_intake or confirmation_project_type == "interpretation":
        consultation.project_intake = next_project_intake
        if confirmation_project_type == "interpretation":
            consultation.project_intake_version = 2

    if preview["project_type"] == "interpretation":
        project, _created = ensure_interpretation_project_for_consultation(
            db,
            consultation,
            created_by,
            order_no=preview["order_no"],
            project_name=preview["project_name"],
            customer_order_no=preview["customer_order_no"],
            email_subject_preview=preview["email_subject_preview"],
        )
        project.customer_order_no = preview["customer_order_no"]
        db.flush()
    elif preview["project_type"] == "translation":
        project = db.query(TranslationProject).filter(
            TranslationProject.consultation_id == consultation.id
        ).first()
        if project:
            project.project_name = preview["project_name"]
            project.email_subject_preview = preview["email_subject_preview"]
            if project.project_status in (None, "", "pending", "pending_confirmation"):
                project.project_status = PROJECT_CONFIRMED_STATUS
            db.flush()
        else:
            project_data = TranslationProjectCreate(
                project_name=preview["project_name"],
                task_type="笔译项目",
                consultation_id=consultation.id,
                client_id=consultation.client_id,
                sub_client_id=consultation.sub_client_id,
                customer_order_no=consultation.customer_order_no,
                customer_reception_time=consultation.consultation_time,
                project_status=PROJECT_CONFIRMED_STATUS,
                email_subject_preview=preview["email_subject_preview"],
                created_by=created_by,
            )
            project = create_translation_project(
                db,
                project_data,
                commit=False,
                order_no=preview["order_no"],
            )
    elif preview["project_type"] == "annotation":
        project, _created = ensure_annotation_project_for_consultation(
            db, consultation, created_by, order_no=preview["order_no"],
            project_name=preview["project_name"], email_subject_preview=preview["email_subject_preview"],
        )
    else:
        project, _created = ensure_recruitment_project_for_consultation(
            db, consultation, created_by, order_no=preview["order_no"],
            project_name=preview["project_name"], email_subject_preview=preview["email_subject_preview"],
        )
    apply_intake(
        db, project_type=preview["project_type"], project=project,
        intake=confirmation.project_intake or consultation.project_intake,
        sub_client_id=consultation.sub_client_id, contact_name=consultation.contact_name,
        customer_order_no=consultation.customer_order_no or confirmation.customer_order_no,
        updated_by=created_by,
    )
    return project, preview


def _send_confirmation_mail(
    db: Session,
    consultation,
    project,
    preview: dict,
    confirmation,
    actor: AppUser,
):
    if not confirmation.to_user_ids:
        return None
    payload = BusinessMailSendRequest(
        project_type=preview["project_type"], project_id=project.id,
        consultation_id=consultation.id, source_kind="consultation_confirmation",
        to_user_ids=confirmation.to_user_ids, cc_user_ids=confirmation.cc_user_ids,
        subject=(confirmation.email_subject or preview["email_subject_preview"]).strip(),
        body=(confirmation.email_body or preview.get("email_body") or "").strip(),
        idempotency_key=confirmation.idempotency_key or f"consultation-{consultation.id}-{uuid4()}",
    )
    return serialize_mail(create_and_send(db, payload, actor))


def _attach_linked_project_ids(db: Session, consultation):
    translation_project_id = db.query(TranslationProject.id).filter(
        TranslationProject.consultation_id == consultation.id
    ).scalar()
    interpretation_project_id = db.query(InterpretationProject.id).filter(
        InterpretationProject.consultation_id == consultation.id
    ).scalar()
    annotation_project_id = db.query(AnnotationProject.id).filter(
        AnnotationProject.consultation_id == consultation.id
    ).scalar()
    recruitment_project_id = db.query(RecruitmentProject.id).filter(
        RecruitmentProject.consultation_id == consultation.id
    ).scalar()
    consultation.translation_project_id = translation_project_id
    consultation.interpretation_project_id = interpretation_project_id
    consultation.annotation_project_id = annotation_project_id
    consultation.recruitment_project_id = recruitment_project_id
    return consultation


@router.post(
    "/confirmation-preview",
    response_model=ConsultationConfirmationPreviewResponse,
)
def preview_consultation_confirmation(
    payload: ConsultationConfirmationPreviewRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return _confirmation_preview_values(db, payload, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/confirm",
    response_model=ConsultationConfirmationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_confirmed_consultation(
    body: CreateConfirmedConsultationRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        _confirmation_project_type(body.consultation.consultation_type)
        confirmed_payload = body.consultation.model_copy(
            update={"status": CONSULTATION_CONFIRMED_STATUS}
        )
        consultation = create_consultation(
            db,
            confirmed_payload,
            commit=False,
        )
        project, preview = _confirm_consultation_project(
            db,
            consultation,
            body.confirmation,
            current_user.id,
            current_user=current_user,
        )
        db.commit()
        mail = _send_confirmation_mail(
            db, consultation, project, preview, body.confirmation, current_user
        )
        saved = _attach_linked_project_ids(
            db, get_consultation(db, consultation.id)
        )
        return {
            "consultation": saved,
            "project_type": preview["project_type"],
            "project_id": project.id,
            "order_no": project.order_no,
            "email_subject_preview": preview["email_subject_preview"],
            "mail": mail,
        }
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        db.rollback()
        raise


@router.post(
    "/{consultation_id}/confirm",
    response_model=ConsultationConfirmationResponse,
)
def update_confirmed_consultation(
    consultation_id: UUID,
    body: UpdateConfirmedConsultationRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    existing = get_consultation(db, consultation_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="咨询记录不存在")
    update_payload = body.consultation or ConsultationUpdate()
    target_type = (
        update_payload.consultation_type
        if "consultation_type" in update_payload.model_fields_set
        else existing.consultation_type
    )
    try:
        _confirmation_project_type(target_type)
        validate_consultation_project_type_change(db, consultation_id, target_type)
        validate_consultation_annotation_type_change(db, consultation_id, target_type)
        validate_consultation_recruitment_type_change(db, consultation_id, target_type)
        confirmed_payload = update_payload.model_copy(
            update={"status": CONSULTATION_CONFIRMED_STATUS}
        )
        consultation = update_consultation(
            db,
            consultation_id,
            confirmed_payload,
            commit=False,
        )
        project, preview = _confirm_consultation_project(
            db,
            consultation,
            body.confirmation,
            current_user.id,
            current_user=current_user,
        )
        db.commit()
        mail = _send_confirmation_mail(
            db, consultation, project, preview, body.confirmation, current_user
        )
        saved = _attach_linked_project_ids(
            db, get_consultation(db, consultation_id)
        )
        return {
            "consultation": saved,
            "project_type": preview["project_type"],
            "project_id": project.id,
            "order_no": project.order_no,
            "email_subject_preview": preview["email_subject_preview"],
            "mail": mail,
        }
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        db.rollback()
        raise


@router.post("/", response_model=ConsultationResponse, status_code=status.HTTP_201_CREATED)
def create_consultation_endpoint(
    consultation: ConsultationCreate,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key", max_length=128),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        db_consultation = create_consultation(
            db=db, consultation=consultation, idempotency_key=idempotency_key, commit=False
        )
        if (
            db_consultation.status == CONSULTATION_CONFIRMED_STATUS
            and is_interpretation_type(db_consultation.consultation_type)
        ):
            ensure_interpretation_project_for_consultation(
                db, db_consultation, current_user.id
            )
        elif (
            db_consultation.status == CONSULTATION_CONFIRMED_STATUS
            and is_annotation_type(db_consultation.consultation_type)
        ):
            ensure_annotation_project_for_consultation(
                db, db_consultation, current_user.id
            )
        elif (
            db_consultation.status == CONSULTATION_CONFIRMED_STATUS
            and is_recruitment_type(db_consultation.consultation_type)
        ):
            ensure_recruitment_project_for_consultation(
                db, db_consultation, current_user.id
            )
        db.commit()
        return _attach_linked_project_ids(
            db, get_consultation(db, db_consultation.id)
        )
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.query(Consultation).filter(
                Consultation.idempotency_key == idempotency_key
            ).first()
            if existing:
                return _attach_linked_project_ids(db, get_consultation(db, existing.id))
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/count")
def read_consultation_count(
    keyword: Optional[str] = None,
    consultation_code: Optional[str] = None,
    client_name: Optional[str] = None,
    status: Optional[str] = None,
    consultation_date_start: Optional[date] = None,
    consultation_date_end: Optional[date] = None,
    consultation_method: Optional[str] = None,
    consultation_type: Optional[str] = None,
    client_source: Optional[str] = None,
    customer_service_id: Optional[UUID] = None,
    sales_person_id: Optional[UUID] = None,
    follow_up_person_id: Optional[UUID] = None,
    follow_up_status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    return {
        "total": count_consultations(
            db,
            keyword=keyword,
            consultation_code=consultation_code,
            client_name=client_name,
            status=status,
            consultation_date_start=consultation_date_start,
            consultation_date_end=consultation_date_end,
            consultation_method=consultation_method,
            consultation_type=consultation_type,
            client_source=client_source,
            customer_service_id=customer_service_id,
            sales_person_id=sales_person_id,
            follow_up_person_id=follow_up_person_id,
            follow_up_status=follow_up_status,
        )
    }


@router.get("/", response_model=List[ConsultationResponse])
def read_consultations(
    skip: int = 0, 
    limit: int = Query(100, ge=1, le=500), 
    keyword: Optional[str] = None,
    consultation_code: Optional[str] = None,
    client_name: Optional[str] = None,
    status: Optional[str] = None,
    consultation_date_start: Optional[date] = None,
    consultation_date_end: Optional[date] = None,
    consultation_method: Optional[str] = None,
    consultation_type: Optional[str] = None,
    client_source: Optional[str] = None,
    customer_service_id: Optional[UUID] = None,
    sales_person_id: Optional[UUID] = None,
    follow_up_person_id: Optional[UUID] = None,
    follow_up_status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    return get_consultations(
        db, 
        skip=skip, 
        limit=limit,
        keyword=keyword,
        consultation_code=consultation_code,
        client_name=client_name,
        status=status,
        consultation_date_start=consultation_date_start,
        consultation_date_end=consultation_date_end,
        consultation_method=consultation_method,
        consultation_type=consultation_type,
        client_source=client_source,
        customer_service_id=customer_service_id,
        sales_person_id=sales_person_id,
        follow_up_person_id=follow_up_person_id,
        follow_up_status=follow_up_status,
    )


@router.get("/{consultation_id}", response_model=ConsultationResponse)
def read_consultation(consultation_id: UUID, db: Session = Depends(get_db)):
    db_consultation = get_consultation(db, consultation_id=consultation_id)
    if not db_consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    return _attach_linked_project_ids(db, db_consultation)


@router.patch(
    "/{consultation_id}/text-field",
    response_model=ConsultationResponse,
    dependencies=[Depends(require_any_permission("consultations:write"))],
)
def update_consultation_text_field(
    consultation_id: UUID,
    payload: TextFieldUpdate,
    db: Session = Depends(get_db),
):
    consultation = db.get(Consultation, consultation_id)
    if not consultation:
        raise HTTPException(status_code=404, detail="咨询记录不存在")
    try:
        changed = apply_text_field_update(
            consultation,
            payload,
            CONSULTATION_TEXT_FIELDS,
        )
        if changed:
            db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _attach_linked_project_ids(
        db,
        get_consultation(db, consultation_id=consultation_id),
    )


@router.patch(
    "/{consultation_id}/intake-text-field",
    response_model=ConsultationResponse,
    dependencies=[Depends(require_any_permission("consultations:write"))],
)
def update_consultation_intake_text_field(
    consultation_id: UUID,
    payload: TextFieldUpdate,
    db: Session = Depends(get_db),
):
    consultation = db.get(Consultation, consultation_id)
    if not consultation:
        raise HTTPException(status_code=404, detail="咨询记录不存在")
    try:
        project_type = _confirmation_project_type(consultation.consultation_type)
        rules = CONSULTATION_INTAKE_TEXT_FIELDS[project_type]
        rule = rules.get(payload.field)
        if rule is None:
            raise ValueError("该售前字段不支持快捷编辑")
        assert_fresh(consultation, payload.expected_updated_at)
        value = normalize_text_value(payload.value, rule)
        merged = dict(consultation.project_intake or {})
        merged[payload.field] = value
        normalized = validated_intake(project_type, merged)
        if normalized != (consultation.project_intake or {}):
            consultation.project_intake = normalized
            consultation.updated_at = datetime.now()
            db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return _attach_linked_project_ids(
        db,
        get_consultation(db, consultation_id=consultation_id),
    )


@router.put("/{consultation_id}", response_model=ConsultationResponse)
def update_consultation_endpoint(
    consultation_id: UUID,
    consultation_update: ConsultationUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    existing = get_consultation(db, consultation_id=consultation_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    target_type = (
        consultation_update.consultation_type
        if "consultation_type" in consultation_update.model_fields_set
        else existing.consultation_type
    )
    try:
        validate_consultation_project_type_change(db, consultation_id, target_type)
        validate_consultation_annotation_type_change(db, consultation_id, target_type)
        validate_consultation_recruitment_type_change(db, consultation_id, target_type)
        db_consultation = update_consultation(
            db,
            consultation_id=consultation_id,
            consultation_update=consultation_update,
            commit=False,
        )
        if (
            db_consultation.status == CONSULTATION_CONFIRMED_STATUS
            and is_interpretation_type(db_consultation.consultation_type)
        ):
            ensure_interpretation_project_for_consultation(
                db, db_consultation, current_user.id
            )
        elif (
            db_consultation.status == CONSULTATION_CONFIRMED_STATUS
            and is_annotation_type(db_consultation.consultation_type)
        ):
            ensure_annotation_project_for_consultation(
                db, db_consultation, current_user.id
            )
        elif (
            db_consultation.status == CONSULTATION_CONFIRMED_STATUS
            and is_recruitment_type(db_consultation.consultation_type)
        ):
            ensure_recruitment_project_for_consultation(
                db, db_consultation, current_user.id
            )
        db.commit()
        return _attach_linked_project_ids(
            db, get_consultation(db, consultation_id)
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{consultation_id}/create-project", response_model=TranslationProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_from_consultation(
    consultation_id: UUID,
    body: CreateProjectFromConsultationRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """
    基于已确认的咨询记录创建翻译项目。
    项目名称默认复用项目详情的“客户简称-日期-批次”命名规则。
    避免重复：同一条咨询只能生成一个翻译项目。
    """
    db_consultation = get_consultation(db, consultation_id=consultation_id)
    if not db_consultation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="咨询记录不存在")

    if db_consultation.status != CONSULTATION_CONFIRMED_STATUS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有已确认的咨询才能生成项目详情")

    if is_interpretation_type(db_consultation.consultation_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="口译咨询在确认时自动生成口译项目，无需再次生成",
        )

    if not is_translation_type(db_consultation.consultation_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该咨询类型不生成笔译项目，请使用对应的专用项目模块",
        )

    existing_project = (
        db.query(TranslationProject)
        .filter(TranslationProject.consultation_id == consultation_id)
        .first()
    )
    if existing_project:
        if existing_project.project_status in (None, "", "pending", "pending_confirmation"):
            existing_project.project_status = PROJECT_CONFIRMED_STATUS
            db.commit()
            db.refresh(existing_project)
        return existing_project

    project_name = (body.project_name or "").strip() or build_auto_project_name(
        getattr(db_consultation, "client_short_name", None)
    )
    if not project_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="客户简称缺失，无法按规则生成项目名称",
        )

    project_data = TranslationProjectCreate(
        project_name=project_name,
        task_type=CONSULTATION_TASK_TYPE_LABELS.get(
            db_consultation.consultation_type,
            db_consultation.consultation_type,
        ),
        consultation_id=db_consultation.id,
        client_id=db_consultation.client_id,
        customer_reception_time=db_consultation.consultation_time,
        project_status=PROJECT_CONFIRMED_STATUS,
        created_by=current_user.id,
    )

    new_project = create_translation_project(db, project_data)
    return new_project


@router.delete("/{consultation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_consultation_endpoint(consultation_id: UUID, db: Session = Depends(get_db)):
    try:
        success = delete_consultation(db, consultation_id=consultation_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该咨询仍被其他业务数据引用，不能删除")
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")
    return None
