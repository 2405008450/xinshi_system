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
from daily_report_mail_models import DailyReportMailPolicyGroup
from interpretation_models import InterpretationLanguage, InterpretationProject
from annotation_schemas import ANNOTATION_PROJECT_TYPE_LABELS
from interpretation_schemas import PROJECT_TYPE_LABELS as INTERPRETATION_TYPE_LABELS
from mail_service import SmtpSettings, send_text_email
from models import AppUser, Consultation, TranslationProject
from recruitment_models import RecruitmentProject
from word_count_service import get_word_count_matrix
from user_mail_account_service import (
    display_user,
    project_mail_sender_mode,
    resolve_project_sender,
    valid_email,
)


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


def _nested_value(item, key):
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _format_mail_datetime(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    text_value = _clean(value)
    if not text_value:
        return ""
    try:
        return datetime.fromisoformat(text_value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return text_value


def _item_get(item, *keys):
    if isinstance(item, dict):
        for key in keys:
            if key in item and item[key] not in (None, ""):
                return item[key]
        return None
    for key in keys:
        value = getattr(item, key, None)
        if value not in (None, ""):
            return value
    return None


def _language_labels(db: Session, language_ids: set) -> dict:
    cleaned = {language_id for language_id in language_ids if language_id}
    if not cleaned:
        return {}
    rows = db.query(InterpretationLanguage).filter(InterpretationLanguage.id.in_(cleaned)).all()
    return {str(row.id): row.label for row in rows}


def _normalize_interpretation_mail_values(db: Session, values: dict) -> dict:
    """将口译售前内部值转换为邮件中可直接阅读的业务文本。"""
    normalized = dict(values)
    normalized["project_types"] = [
        INTERPRETATION_TYPE_LABELS.get(_clean(item), _clean(item))
        for item in (values.get("project_types") or [])
        if _clean(item)
    ]

    time_ranges = []
    for item in values.get("time_ranges") or []:
        if isinstance(item, str):
            if _clean(item):
                time_ranges.append(_clean(item))
            continue
        start = _format_mail_datetime(_item_get(item, "scheduled_start", "scheduledStart"))
        end = _format_mail_datetime(_item_get(item, "scheduled_end", "scheduledEnd"))
        if start and end:
            time_ranges.append(f"{start} 至 {end}")
    normalized["time_ranges"] = time_ranges

    raw_directions = values.get("language_directions") or []
    direction_ids = {
        language_id
        for item in raw_directions
        if not isinstance(item, str)
        for language_id in (
            _item_get(item, "language_ids", "languageIds")
            or [
                _item_get(item, "source_language_id", "sourceLanguageId"),
                _item_get(item, "target_language_id", "targetLanguageId"),
            ]
        )
        if language_id
    }
    language_labels = _language_labels(db, direction_ids)

    directions = []
    for item in raw_directions:
        if isinstance(item, str):
            if _clean(item):
                directions.append(_clean(item))
            continue
        language_ids = _item_get(item, "language_ids", "languageIds") or [
            _item_get(item, "source_language_id", "sourceLanguageId"),
            _item_get(item, "target_language_id", "targetLanguageId"),
        ]
        labels = [language_labels.get(str(language_id), "") for language_id in language_ids if language_id]
        if len(labels) >= 2 and all(labels):
            required_count = _item_get(item, "required_count", "requiredCount")
            count_text = f"（{required_count}人）" if required_count else "（人数待补充）"
            directions.append(f"{' ↔ '.join(labels)}{count_text}")
    normalized["language_directions"] = directions
    counts = [
        _item_get(item, "required_count", "requiredCount")
        for item in raw_directions
        if not isinstance(item, str)
    ]
    if counts and all(isinstance(value, int) and value > 0 for value in counts):
        normalized["required_interpreter_count"] = sum(counts)
    return normalized


def _normalize_language_item_texts(db: Session, raw_items) -> list[str]:
    items = []
    language_ids = {
        language_id
        for item in (raw_items or [])
        if not isinstance(item, str)
        for language_id in (
            _item_get(item, "source_language_id", "sourceLanguageId"),
            _item_get(item, "target_language_id", "targetLanguageId"),
        )
        if language_id
    }
    labels = _language_labels(db, language_ids)
    for item in raw_items or []:
        if isinstance(item, str):
            if _clean(item):
                items.append(_clean(item))
            continue
        source_label = labels.get(str(_item_get(item, "source_language_id", "sourceLanguageId") or ""), "")
        target_label = labels.get(str(_item_get(item, "target_language_id", "targetLanguageId") or ""), "")
        if source_label and target_label:
            items.append(f"{source_label} → {target_label}")
        elif source_label:
            items.append(source_label)
    return items


def _normalize_annotation_mail_values(db: Session, values: dict) -> dict:
    """将标注售前内部值转换为邮件中可直接阅读的业务文本。"""
    normalized = dict(values)
    normalized["project_types"] = [
        ANNOTATION_PROJECT_TYPE_LABELS.get(_clean(item), _clean(item))
        for item in (values.get("project_types") or [])
        if _clean(item)
    ]
    normalized["language_items"] = _normalize_language_item_texts(db, values.get("language_items"))
    return normalized


def _normalize_recruitment_mail_values(db: Session, values: dict) -> dict:
    normalized = dict(values)
    normalized["language_directions"] = _normalize_language_item_texts(db, values.get("language_directions"))
    return normalized


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
    if db.query(DailyReportMailPolicyGroup.id).filter(DailyReportMailPolicyGroup.group_id == group_id).first():
        raise ValueError("邮件组正在被工作报告收件策略使用，请先解除引用")
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
    if not all_ids:
        raise ValueError("至少需要配置一个默认主送组或抄送组")
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
    if not to_users and not cc_users:
        raise ValueError("默认邮件组中没有可用用户")
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
    "translation": (("项目名称", "project_name"), ("服务内容", "service_content"), ("翻译方向", "language_pair")),
    "interpretation": (("项目名称", "project_name"), ("项目类型", "project_types"), ("预定时段", "time_ranges"), ("地点", "locations"), ("口译方向", "language_directions"), ("总需求人数", "required_interpreter_count")),
    "annotation": (("项目名称", "project_name"), ("项目类型", "project_types"), ("具体任务", "task_description"), ("语言范围", "language_items")),
    "recruitment": (("项目名称", "project_name"), ("职位名称/类型", "position_title"), ("招聘人数", "headcount_min"), ("拟履职开始日期", "employment_start"), ("拟履职结束日期", "employment_end"), ("任职工作属地", "work_location")),
}


BODY_LABELS = {
    "translation": (("服务内容", "service_content"), ("文本类型", "file_type_secondary"), ("翻译方向", "language_pair"), ("客户交稿时间", "customer_deadline_time"), ("优先级", "priority"), ("专业要求", "customer_requirement_professional"), ("特殊要求", "customer_requirement_special")),
    "interpretation": (("口译类型", "project_types"), ("具体任务", "task_description"), ("预定时段", "time_ranges"), ("地点", "locations"), ("口译方向", "language_directions"), ("客户预算", "customer_budget"), ("总需求人数", "required_interpreter_count"), ("译员性别", "required_interpreter_gender"), ("口译水平", "required_interpretation_level"), ("口译领域", "interpretation_domain"), ("口译内容", "interpretation_content"), ("特殊要求", "interpreter_special_requirements")),
    "annotation": (("项目类型", "project_types"), ("具体任务", "task_description"), ("潜在需求量", "potential_demand"), ("语言范围", "language_items"), ("客户价格", "price_items")),
    "recruitment": (("职位名称/类型", "position_title"), ("职位描述", "job_description"), ("招聘人数下限", "headcount_min"), ("招聘人数上限", "headcount_max"), ("外语/翻译方向", "language_directions"), ("拟履职开始", "employment_start"), ("拟履职结束", "employment_end"), ("任职工作属地", "work_location"), ("拟入职日期", "target_onboard_date"), ("服务费用类型", "service_fee_type"), ("服务费用金额", "service_fee_amount"), ("服务费用比例", "service_fee_rate"), ("费用说明", "service_fee_note")),
}


WORD_COUNT_METRIC_LABELS = (
    ("words", "字数"),
    ("characters_no_spaces", "字符数（不计空格）"),
    ("cjk_chars_korean_words", "中文字符和朝鲜语单词"),
    ("foreign_words", "外文字数"),
    ("documents", "份数"),
    ("pages", "页数"),
)


def _format_word_count_lines(matrix: Optional[dict]) -> list[str]:
    """把项目字数统计完整转换为适合纯文本邮件阅读的行。"""
    if not isinstance(matrix, dict):
        return []

    dimensions = [
        ("我司字数", matrix.get("company")),
        ("客户字数", matrix.get("customer")),
        ("译员预定（项目预估）", matrix.get("translator_estimate") or matrix.get("translatorEstimate")),
    ]
    for translator in matrix.get("translators") or []:
        name = _clean(_nested_value(translator, "translator_name")) or "当前译员"
        dimensions.extend((
            (f"{name} · 预定", _nested_value(translator, "planned")),
            (f"{name} · 实际", _nested_value(translator, "actual")),
        ))

    result = []
    for dimension_label, raw_values in dimensions:
        values = raw_values if isinstance(raw_values, dict) else {}
        metrics = []
        for key, label in WORD_COUNT_METRIC_LABELS:
            value = values.get(key)
            if value is None or value == "":
                continue
            try:
                value_text = f"{int(value):,}"
            except (TypeError, ValueError):
                value_text = _clean(value)
            metrics.append(f"{label} {value_text}")
        if metrics:
            result.append(f"  {dimension_label}：{'；'.join(metrics)}")
    return result


def build_preview(
    db: Session,
    project_type: str,
    *,
    project_id: Optional[UUID] = None,
    source: Optional[dict] = None,
    current_user: Optional[AppUser] = None,
) -> dict:
    if project_type not in PROJECT_MAIL_TYPES:
        raise ValueError("不支持的项目类型")
    values = dict(source or {})
    if project_id:
        project = db.query(PROJECT_MODELS[project_type]).filter(PROJECT_MODELS[project_type].id == project_id).first()
        if not project:
            raise LookupError("项目不存在")
        project_values = _project_source(project_type, project)
        if project_type == "translation":
            project_values["word_count_matrix"] = get_word_count_matrix(db, "project", project.id)
        values = {**project_values, **values}
    if project_type == "interpretation":
        values = _normalize_interpretation_mail_values(db, values)
    elif project_type == "annotation":
        values = _normalize_annotation_mail_values(db, values)
    elif project_type == "recruitment":
        values = _normalize_recruitment_mail_values(db, values)
    blocking: list[str] = []
    try:
        to_users, cc_users = policy_recipients(db, project_type)
    except ValueError as exc:
        to_users, cc_users = [], []
        blocking.append(str(exc))
    sender_view = {
        "sender_mode": "system",
        "sender_name": None,
        "sender_email": None,
        "sender_verified": False,
    }
    try:
        sender_mode = project_mail_sender_mode()
        if sender_mode == "personal" and current_user is None:
            raise ValueError("无法识别当前发件用户，请重新登录后再试")
        _settings, sender_view = resolve_project_sender(db, current_user)
    except Exception as exc:
        sender_view["sender_mode"] = locals().get("sender_mode", "system")
        if current_user is not None and sender_view["sender_mode"] == "personal":
            sender_view.update(
                sender_name=display_user(current_user),
                sender_email=valid_email(current_user.email),
            )
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
        ("客户简称", values.get("client_short_name")), ("客户经理联系方式", values.get("manager_contact")),
        ("客户单号/项目标识", values.get("customer_order_no")),
    )
    lines = [f"{label}：{_clean(value)}" for label, value in common if _clean(value)]
    core_body_keys = {key for _label, key in CORE_FIELDS[project_type]}
    # 核心字段为空时也要在邮件预览中保留对应行，避免用户只能从“缺失字段”标签猜测正文缺了什么。
    # 缺失核心字段会继续阻止发送，因此“（待填写）”只用于预览提示，不会进入实际投递邮件。
    lines.extend(
        f"{label}：{_clean(values.get(key)) or '（待填写）'}"
        for label, key in BODY_LABELS[project_type]
        if _clean(values.get(key)) or key in core_body_keys
    )
    word_count_lines = _format_word_count_lines(values.get("word_count_matrix")) if project_type == "translation" else []
    if word_count_lines:
        lines.extend(["项目字数统计：", *word_count_lines])
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
        **sender_view,
        "can_send": not blocking, "blocking_reasons": blocking,
    }


def _project_id(mail: BusinessMail) -> Optional[UUID]:
    return getattr(mail, PROJECT_FK_FIELDS[mail.project_type])


def serialize_mail(mail: BusinessMail) -> dict:
    attempts = sorted(
        list(mail.attempts or []),
        key=lambda item: item.attempted_at or datetime.min,
    )
    latest_attempt = attempts[-1] if attempts else None
    return {
        "id": mail.id, "source_kind": mail.source_kind, "project_type": mail.project_type,
        "consultation_id": mail.consultation_id, "project_id": _project_id(mail),
        "subject": mail.subject, "body": mail.body, "status": mail.status,
        "recipients": [{
            "user_id": item.user_id, "display_name": item.display_name_snapshot,
            "email": item.email_snapshot, "department": None, "recipient_type": item.recipient_type,
        } for item in mail.recipients],
        "sender_name": latest_attempt.sender_name_snapshot if latest_attempt else None,
        "sender_email": latest_attempt.sender_email_snapshot if latest_attempt else None,
        "attempts": [{
            "attempted_at": item.attempted_at,
            "sender_user_id": item.sender_user_id,
            "sender_name": item.sender_name_snapshot,
            "sender_email": item.sender_email_snapshot,
            "success": item.success,
            "delivery_mode": item.delivery_mode,
            "error": item.error,
        } for item in attempts],
        "send_error": mail.send_error, "delivery_mode": mail.delivery_mode,
        "created_at": mail.created_at, "send_attempted_at": mail.send_attempted_at, "sent_at": mail.sent_at,
    }


def _deliver(db: Session, mail: BusinessMail, actor: AppUser) -> BusinessMail:
    to_emails = [item.email_snapshot for item in mail.recipients if item.recipient_type == "to"]
    cc_emails = [item.email_snapshot for item in mail.recipients if item.recipient_type == "cc"]
    now = datetime.now()
    mail.status = "sending"
    mail.send_attempted_at = now
    mail.send_error = None
    db.commit()
    attempt = BusinessMailAttempt(
        mail_id=mail.id,
        sender_user_id=actor.id,
        sender_name_snapshot=display_user(actor),
        sender_email_snapshot=valid_email(actor.email),
    )
    db.add(attempt)
    try:
        settings, sender_view = resolve_project_sender(db, actor)
        attempt.sender_user_id = actor.id if sender_view["sender_mode"] == "personal" else None
        attempt.sender_name_snapshot = sender_view["sender_name"]
        attempt.sender_email_snapshot = sender_view["sender_email"]
        attempt.delivery_mode = settings.mode
        mail.delivery_mode = settings.mode
        result = send_text_email(
            to_emails=to_emails, cc_emails=cc_emails, subject=mail.subject,
            body=mail.body, message_id=mail.smtp_message_id, settings=settings,
        )
        mail.status = "sent"
        mail.sent_at = now
        mail.delivery_mode = result.delivery_mode
        attempt.delivery_mode = result.delivery_mode
        attempt.actual_recipients = result.delivery_recipient
        attempt.success = True
    except Exception as exc:
        mail.status = "failed"
        mail.send_error = str(exc)[:5000]
        attempt.error = mail.send_error
        attempt.success = False
    db.commit()
    return db.query(BusinessMail).options(
        joinedload(BusinessMail.recipients), joinedload(BusinessMail.attempts)
    ).filter(BusinessMail.id == mail.id).first()


def create_and_send(db: Session, payload, actor: AppUser) -> BusinessMail:
    existing = db.query(BusinessMail).options(
        joinedload(BusinessMail.recipients), joinedload(BusinessMail.attempts)
    ).filter(BusinessMail.idempotency_key == payload.idempotency_key).first()
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
        created_by=actor.id,
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
        existing = db.query(BusinessMail).options(
            joinedload(BusinessMail.recipients), joinedload(BusinessMail.attempts)
        ).filter(
            BusinessMail.idempotency_key == payload.idempotency_key
        ).first()
        if existing:
            return existing
        raise
    return _deliver(db, mail, actor)


def retry_mail(db: Session, mail_id: UUID, actor: AppUser) -> BusinessMail:
    mail = db.query(BusinessMail).options(
        joinedload(BusinessMail.recipients), joinedload(BusinessMail.attempts)
    ).filter(BusinessMail.id == mail_id).first()
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
    return _deliver(db, mail, actor)


def list_mails(db: Session, *, consultation_id: Optional[UUID] = None, project_type: Optional[str] = None, project_id: Optional[UUID] = None) -> list[BusinessMail]:
    if project_type and project_type not in PROJECT_MAIL_TYPES:
        raise ValueError("不支持的项目类型")
    query = db.query(BusinessMail).options(
        joinedload(BusinessMail.recipients), joinedload(BusinessMail.attempts)
    )
    if consultation_id:
        query = query.filter(BusinessMail.consultation_id == consultation_id)
    if project_type:
        query = query.filter(BusinessMail.project_type == project_type)
        if project_id:
            query = query.filter(getattr(BusinessMail, PROJECT_FK_FIELDS[project_type]) == project_id)
    return query.order_by(BusinessMail.created_at.desc()).all()
