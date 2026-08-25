"""内部项目邮件组、模板、发送与审计服务。"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from annotation_models import AnnotationProject
from business_mail_models import (
    BusinessMail,
    BusinessMailAttempt,
    BusinessMailRecipient,
    MailRecipientGroup,
    MailRecipientGroupMember,
    PROJECT_MAIL_TYPES,
    ProjectMailPolicy,
    ProjectMailPolicyGroup,
)
from interpretation_models import InterpretationProject
from mail_service import SmtpSettings, send_text_email
from models import AppUser, Consultation, TranslationProject
from recruitment_models import RecruitmentProject


PROJECT_MODELS = {
    "translation": TranslationProject,
    "interpretation": InterpretationProject,
    "annotation": AnnotationProject,
    "recruitment": RecruitmentProject,
}
PROJECT_FK_FIELDS = {
    "translation": "translation_project_id",
    "interpretation": "interpretation_project_id",
    "annotation": "annotation_project_id",
    "recruitment": "recruitment_project_id",
}
TYPE_LABELS = {
    "translation": "笔译",
    "interpretation": "口译",
    "annotation": "标注",
    "recruitment": "招聘",
}


def _clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "；".join(_clean(item) for item in value if _clean(item))
    return str(value).strip()


def _valid_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return validate_email(value, check_deliverability=False).normalized
    except EmailNotValidError:
        return None


def validate_internal_users(db: Session, user_ids: Iterable[UUID]) -> list[AppUser]:
    ordered_ids = list(dict.fromkeys(user_ids))
    rows = db.query(AppUser).filter(AppUser.id.in_(ordered_ids)).all() if ordered_ids else []
    by_id = {row.id: row for row in rows}
    invalid = []
    result = []
    for user_id in ordered_ids:
        user = by_id.get(user_id)
        if not user:
            invalid.append(f"用户 {user_id} 不存在")
        elif not user.is_active:
            invalid.append(f"{user.full_name or user.username} 已停用")
        elif not _valid_email(user.email):
            invalid.append(f"{user.full_name or user.username} 未绑定有效邮箱")
        else:
            result.append(user)
    if invalid:
        raise ValueError("；".join(invalid))
    return result


def serialize_user(user: AppUser, recipient_type: str = "to") -> dict:
    return {
        "user_id": user.id,
        "display_name": user.full_name or user.username,
        "email": _valid_email(user.email) or "",
        "department": user.department,
        "recipient_type": recipient_type,
    }


def serialize_group(group: MailRecipientGroup) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "is_active": group.is_active,
        "user_ids": [item.user_id for item in group.members],
        "members": [serialize_user(item.user) for item in group.members if item.user],
        "created_at": group.created_at,
        "updated_at": group.updated_at,
    }


def list_groups(db: Session) -> list[MailRecipientGroup]:
    return db.query(MailRecipientGroup).options(
        joinedload(MailRecipientGroup.members).joinedload(MailRecipientGroupMember.user)
    ).order_by(MailRecipientGroup.name).all()


def save_group(db: Session, payload, actor_id: UUID, group_id: Optional[UUID] = None) -> MailRecipientGroup:
    users = validate_internal_users(db, payload.user_ids)
    name = payload.name.strip()
    duplicate = db.query(MailRecipientGroup.id).filter(MailRecipientGroup.name == name)
    if group_id:
        duplicate = duplicate.filter(MailRecipientGroup.id != group_id)
    if duplicate.first():
        raise ValueError("邮件组名称已存在")
    group = db.query(MailRecipientGroup).filter(MailRecipientGroup.id == group_id).first() if group_id else None
    if group_id and not group:
        raise LookupError("邮件组不存在")
    if not group:
        group = MailRecipientGroup(name=name, created_by=actor_id)
        db.add(group)
        db.flush()
    group.name = name
    group.description = (payload.description or "").strip() or None
    group.is_active = payload.is_active
    group.updated_at = datetime.now()
    group.members.clear()
    db.flush()
    group.members = [MailRecipientGroupMember(user_id=user.id) for user in users]
    db.commit()
    return next(item for item in list_groups(db) if item.id == group.id)


def delete_group(db: Session, group_id: UUID) -> bool:
    group = db.query(MailRecipientGroup).filter(MailRecipientGroup.id == group_id).first()
    if not group:
        return False
    if db.query(ProjectMailPolicyGroup.id).filter(ProjectMailPolicyGroup.group_id == group_id).first():
        raise ValueError("邮件组正在被项目邮件策略使用，请先解除引用")
    db.delete(group)
    db.commit()
    return True


def _policy(db: Session, project_type: str) -> Optional[ProjectMailPolicy]:
    return db.query(ProjectMailPolicy).options(
        joinedload(ProjectMailPolicy.groups)
        .joinedload(ProjectMailPolicyGroup.group)
        .joinedload(MailRecipientGroup.members)
        .joinedload(MailRecipientGroupMember.user)
    ).filter(ProjectMailPolicy.project_type == project_type).first()


def serialize_policy(policy: Optional[ProjectMailPolicy], project_type: str) -> dict:
    links = list(policy.groups) if policy else []
    to_groups = [item.group for item in links if item.recipient_type == "to"]
    cc_groups = [item.group for item in links if item.recipient_type == "cc"]
    return {
        "project_type": project_type,
        "to_group_ids": [item.id for item in to_groups],
        "cc_group_ids": [item.id for item in cc_groups],
        "to_groups": [serialize_group(item) for item in to_groups],
        "cc_groups": [serialize_group(item) for item in cc_groups],
    }


def save_policy(db: Session, project_type: str, payload, actor_id: UUID) -> ProjectMailPolicy:
    if project_type not in PROJECT_MAIL_TYPES:
        raise ValueError("不支持的项目类型")
    to_ids = list(dict.fromkeys(payload.to_group_ids))
    cc_ids = [item for item in dict.fromkeys(payload.cc_group_ids) if item not in set(to_ids)]
    all_ids = [*to_ids, *cc_ids]
    groups = db.query(MailRecipientGroup).filter(MailRecipientGroup.id.in_(all_ids)).all() if all_ids else []
    by_id = {item.id: item for item in groups}
    invalid = [str(item) for item in all_ids if item not in by_id or not by_id[item].is_active]
    if invalid:
        raise ValueError(f"邮件组不存在或已停用：{', '.join(invalid)}")
    if not to_ids:
        raise ValueError("至少需要配置一个默认收件组")
    policy = db.query(ProjectMailPolicy).filter(ProjectMailPolicy.project_type == project_type).first()
    if not policy:
        policy = ProjectMailPolicy(project_type=project_type)
        db.add(policy)
        db.flush()
    policy.updated_by = actor_id
    policy.updated_at = datetime.now()
    policy.groups.clear()
    db.flush()
    policy.groups = [
        ProjectMailPolicyGroup(group_id=group_id, recipient_type=recipient_type)
        for recipient_type, ids in (("to", to_ids), ("cc", cc_ids))
        for group_id in ids
    ]
    db.commit()
    return _policy(db, project_type)


def policy_recipients(db: Session, project_type: str) -> tuple[list[AppUser], list[AppUser]]:
    policy = _policy(db, project_type)
    if not policy:
        raise ValueError(f"尚未配置{TYPE_LABELS[project_type]}项目默认邮件组")
    to_ids: list[UUID] = []
    cc_ids: list[UUID] = []
    for link in policy.groups:
        if not link.group or not link.group.is_active:
            raise ValueError("默认邮件组已停用，请管理员修复项目邮件设置")
        target = to_ids if link.recipient_type == "to" else cc_ids
        target.extend(item.user_id for item in link.group.members)
    to_users = validate_internal_users(db, to_ids)
    to_set = {item.id for item in to_users}
    cc_users = validate_internal_users(db, [item for item in cc_ids if item not in to_set])
    if not to_users:
        raise ValueError("默认收件组中没有可用用户")
    return to_users, cc_users


def _project_source(project_type: str, project) -> dict:
    client = getattr(project, "sub_client", None) or getattr(project, "client", None)
    source = {
        "order_no": getattr(project, "order_no", None),
        "project_name": getattr(project, "project_name", None),
        "client_short_name": getattr(client, "client_short_name", None) or getattr(project, "client_short_name", None),
        "manager_contact": getattr(client, "manager_contact", None),
        "customer_order_no": getattr(project, "customer_order_no", None),
    }
    field_names = {
        "translation": ("service_content", "file_type_secondary", "language_pair", "customer_deadline_time", "priority", "customer_requirement_professional", "customer_requirement_special"),
        "interpretation": ("project_types", "task_description", "locations", "customer_budget", "required_interpreter_count", "required_interpreter_gender", "required_interpretation_level", "interpretation_domain", "interpretation_content", "interpreter_special_requirements"),
        "annotation": ("project_types", "task_description", "potential_demand"),
        "recruitment": ("position_title", "job_description", "headcount_min", "headcount_max", "employment_start", "employment_end", "work_location", "target_onboard_date", "service_fee_type", "service_fee_amount", "service_fee_rate", "service_fee_note"),
    }
    source.update({name: getattr(project, name, None) for name in field_names[project_type]})
    if project_type == "interpretation":
        source["time_ranges"] = [
            f"{item.scheduled_start:%Y-%m-%d %H:%M} 至 {item.scheduled_end:%Y-%m-%d %H:%M}"
            for item in (project.time_ranges or [])
        ]
        source["language_directions"] = [item.display for item in (project.language_directions or [])]
    elif project_type == "annotation":
        source["language_items"] = [item.display for item in (project.language_items or [])]
        source["price_items"] = [item.amount_display for item in (project.price_items or [])]
    elif project_type == "recruitment":
        source["language_directions"] = [item.label for item in (project.language_directions or [])]
    return source


CORE_FIELDS = {
    "translation": (("项目名称", "project_name"), ("服务内容", "service_content"), ("翻译方向", "language_pair"), ("客户交期", "customer_deadline_time")),
    "interpretation": (("项目名称", "project_name"), ("项目类型", "project_types"), ("预定时段", "time_ranges"), ("地点", "locations"), ("口译方向", "language_directions"), ("译员人数", "required_interpreter_count")),
    "annotation": (("项目名称", "project_name"), ("项目类型", "project_types"), ("具体任务", "task_description"), ("语言范围", "language_items")),
    "recruitment": (("项目名称", "project_name"), ("职位名称/类型", "position_title"), ("招聘人数", "headcount_min"), ("拟履职开始日期", "employment_start"), ("拟履职结束日期", "employment_end"), ("任职工作属地", "work_location")),
}


BODY_LABELS = {
    "translation": (("服务内容", "service_content"), ("文本类型", "file_type_secondary"), ("翻译方向", "language_pair"), ("客户交期", "customer_deadline_time"), ("优先级", "priority"), ("专业要求", "customer_requirement_professional"), ("特殊要求", "customer_requirement_special")),
    "interpretation": (("项目类型", "project_types"), ("具体任务", "task_description"), ("预定时段", "time_ranges"), ("地点", "locations"), ("口译方向", "language_directions"), ("客户预算", "customer_budget"), ("译员人数", "required_interpreter_count"), ("译员性别", "required_interpreter_gender"), ("口译水平", "required_interpretation_level"), ("口译领域", "interpretation_domain"), ("口译内容", "interpretation_content"), ("特殊要求", "interpreter_special_requirements")),
    "annotation": (("项目类型", "project_types"), ("具体任务", "task_description"), ("潜在需求量", "potential_demand"), ("语言范围", "language_items"), ("客户价格", "price_items")),
    "recruitment": (("职位名称/类型", "position_title"), ("职位描述", "job_description"), ("招聘人数下限", "headcount_min"), ("招聘人数上限", "headcount_max"), ("外语/翻译方向", "language_directions"), ("拟履职开始", "employment_start"), ("拟履职结束", "employment_end"), ("任职工作属地", "work_location"), ("拟入职日期", "target_onboard_date"), ("服务费用类型", "service_fee_type"), ("服务费用金额", "service_fee_amount"), ("服务费用比例", "service_fee_rate"), ("费用说明", "service_fee_note")),
}


def build_preview(db: Session, project_type: str, *, project_id: Optional[UUID] = None, source: Optional[dict] = None) -> dict:
    if project_type not in PROJECT_MAIL_TYPES:
        raise ValueError("不支持的项目类型")
    values = dict(source or {})
    if project_id:
        project = db.query(PROJECT_MODELS[project_type]).filter(PROJECT_MODELS[project_type].id == project_id).first()
        if not project:
            raise LookupError("项目不存在")
        values = {**_project_source(project_type, project), **values}
    blocking: list[str] = []
    try:
        to_users, cc_users = policy_recipients(db, project_type)
    except ValueError as exc:
        to_users, cc_users = [], []
        blocking.append(str(exc))
    try:
        SmtpSettings.from_env().validate()
    except Exception as exc:
        blocking.append(str(exc))
    order_no = _clean(values.get("order_no"))
    project_name = _clean(values.get("project_name"))
    subject_values = [values.get("subject_prefix"), order_no, values.get("client_short_name"), values.get("manager_contact")]
    if project_type != "translation":
        subject_values.append(values.get("customer_order_no"))
    subject_values.append(project_name)
    subject = "，".join(_clean(item) for item in subject_values if _clean(item))
    missing = [label for label, key in CORE_FIELDS[project_type] if not _clean(values.get(key))]
    if not order_no:
        missing.insert(0, "订单号")
    common = (
        ("项目类型", TYPE_LABELS[project_type]), ("订单号", order_no), ("项目名称", project_name),
        ("客户简称", values.get("client_short_name")), ("负责人联系方式", values.get("manager_contact")),
        ("客户单号/项目标识", values.get("customer_order_no")),
    )
    lines = [f"{label}：{_clean(value)}" for label, value in common if _clean(value)]
    lines.extend(f"{label}：{_clean(values.get(key))}" for label, key in BODY_LABELS[project_type] if _clean(values.get(key)))
    if _clean(values.get("consultation_description")):
        lines.append(f"咨询说明：{_clean(values.get('consultation_description'))}")
    if _clean(values.get("remarks")):
        lines.append(f"备注：{_clean(values.get('remarks'))}")
    body = "\n".join(lines)
    if missing:
        blocking.append(f"请先填写核心字段：{'、'.join(missing)}")
    if not subject:
        blocking.append("邮件主题不能为空")
    if not body:
        blocking.append("邮件正文不能为空")
    return {
        "project_type": project_type, "order_no": order_no or None, "project_name": project_name or None,
        "to_users": [serialize_user(item, "to") for item in to_users],
        "cc_users": [serialize_user(item, "cc") for item in cc_users],
        "subject": subject, "body": body, "missing_fields": missing,
        "can_send": not blocking, "blocking_reasons": blocking,
    }


def _project_id(mail: BusinessMail) -> Optional[UUID]:
    return getattr(mail, PROJECT_FK_FIELDS[mail.project_type])


def serialize_mail(mail: BusinessMail) -> dict:
    return {
        "id": mail.id, "source_kind": mail.source_kind, "project_type": mail.project_type,
        "consultation_id": mail.consultation_id, "project_id": _project_id(mail),
        "subject": mail.subject, "body": mail.body, "status": mail.status,
        "recipients": [{
            "user_id": item.user_id, "display_name": item.display_name_snapshot,
            "email": item.email_snapshot, "department": None, "recipient_type": item.recipient_type,
        } for item in mail.recipients],
        "send_error": mail.send_error, "delivery_mode": mail.delivery_mode,
        "created_at": mail.created_at, "send_attempted_at": mail.send_attempted_at, "sent_at": mail.sent_at,
    }


def _deliver(db: Session, mail: BusinessMail) -> BusinessMail:
    to_emails = [item.email_snapshot for item in mail.recipients if item.recipient_type == "to"]
    cc_emails = [item.email_snapshot for item in mail.recipients if item.recipient_type == "cc"]
    now = datetime.now()
    mail.status = "sending"
    mail.send_attempted_at = now
    mail.send_error = None
    db.commit()
    try:
        result = send_text_email(
            to_emails=to_emails, cc_emails=cc_emails, subject=mail.subject,
            body=mail.body, message_id=mail.smtp_message_id,
        )
        mail.status = "sent"
        mail.sent_at = now
        mail.delivery_mode = result.delivery_mode
        db.add(BusinessMailAttempt(mail_id=mail.id, delivery_mode=result.delivery_mode, actual_recipients=result.delivery_recipient, success=True))
    except Exception as exc:
        mail.status = "failed"
        mail.send_error = str(exc)[:5000]
        db.add(BusinessMailAttempt(mail_id=mail.id, error=mail.send_error, success=False))
    db.commit()
    return db.query(BusinessMail).options(joinedload(BusinessMail.recipients)).filter(BusinessMail.id == mail.id).first()


def create_and_send(db: Session, payload, actor_id: UUID) -> BusinessMail:
    existing = db.query(BusinessMail).options(joinedload(BusinessMail.recipients)).filter(BusinessMail.idempotency_key == payload.idempotency_key).first()
    if existing:
        return existing
    to_users = validate_internal_users(db, payload.to_user_ids)
    to_ids = {item.id for item in to_users}
    cc_users = validate_internal_users(db, [item for item in payload.cc_user_ids if item not in to_ids])
    project = db.query(PROJECT_MODELS[payload.project_type]).filter(PROJECT_MODELS[payload.project_type].id == payload.project_id).first()
    if not project:
        raise LookupError("项目不存在")
    project_consultation_id = getattr(project, "consultation_id", None)
    if payload.consultation_id and project_consultation_id != payload.consultation_id:
        raise ValueError("咨询记录与项目不匹配")
    mail = BusinessMail(
        source_kind=payload.source_kind, project_type=payload.project_type,
        consultation_id=payload.consultation_id, subject=payload.subject.strip(), body=payload.body.strip(),
        idempotency_key=payload.idempotency_key, smtp_message_id=f"<project-mail-{payload.idempotency_key}@xinshi-system.local>",
        created_by=actor_id,
    )
    setattr(mail, PROJECT_FK_FIELDS[payload.project_type], payload.project_id)
    db.add(mail)
    db.flush()
    mail.recipients = [
        BusinessMailRecipient(user_id=user.id, recipient_type=kind, display_name_snapshot=user.full_name or user.username, email_snapshot=_valid_email(user.email) or "")
        for kind, users in (("to", to_users), ("cc", cc_users)) for user in users
    ]
    if hasattr(project, "email_subject_preview"):
        project.email_subject_preview = mail.subject
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(BusinessMail).options(joinedload(BusinessMail.recipients)).filter(
            BusinessMail.idempotency_key == payload.idempotency_key
        ).first()
        if existing:
            return existing
        raise
    return _deliver(db, mail)


def retry_mail(db: Session, mail_id: UUID) -> BusinessMail:
    mail = db.query(BusinessMail).options(joinedload(BusinessMail.recipients)).filter(BusinessMail.id == mail_id).first()
    if not mail:
        raise LookupError("邮件记录不存在")
    if mail.status != "failed":
        raise ValueError("只有发送失败的邮件可以直接重试")
    if any(item.user_id is None for item in mail.recipients):
        raise ValueError("原收件用户已删除，请重新创建邮件")
    users = validate_internal_users(db, [item.user_id for item in mail.recipients])
    current_emails = {item.id: (_valid_email(item.email) or "") for item in users}
    if any(current_emails.get(item.user_id) != item.email_snapshot for item in mail.recipients):
        raise ValueError("收件用户邮箱已变化，请重新创建邮件")
    return _deliver(db, mail)


def list_mails(db: Session, *, consultation_id: Optional[UUID] = None, project_type: Optional[str] = None, project_id: Optional[UUID] = None) -> list[BusinessMail]:
    if project_type and project_type not in PROJECT_MAIL_TYPES:
        raise ValueError("不支持的项目类型")
    query = db.query(BusinessMail).options(joinedload(BusinessMail.recipients))
    if consultation_id:
        query = query.filter(BusinessMail.consultation_id == consultation_id)
    if project_type:
        query = query.filter(BusinessMail.project_type == project_type)
        if project_id:
            query = query.filter(getattr(BusinessMail, PROJECT_FK_FIELDS[project_type]) == project_id)
    return query.order_by(BusinessMail.created_at.desc()).all()
