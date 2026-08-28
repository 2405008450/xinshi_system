"""个人工作日报的邮箱绑定、收件策略、预览与发送服务。"""

from __future__ import annotations

import datetime
import html
from dataclasses import replace
from typing import Optional
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.orm import Session, joinedload

from business_mail_models import MailRecipientGroup, MailRecipientGroupMember
from crypto_utils import decrypt_credential, encrypt_credential
from daily_report_mail_models import (
    DailyReportMailAttempt,
    DailyReportMailDelivery,
    DailyReportMailPolicy,
    DailyReportMailPolicyGroup,
    DailyReportMailRecipient,
    UserMailAccount,
)
from mail_service import (
    MailConfigurationError,
    MailDeliveryError,
    SmtpSettings,
    get_mail_status,
    send_text_email,
    verify_smtp_settings,
)
from models import AppUser
from task_models import DailyReport


SOURCE_LABELS = {"project": "项目任务", "non_project": "非项目任务", "manual": "手工补充"}
MAIL_COLUMNS = (
    ("order_no", "订单号"),
    ("task_name", "项目 / 任务"),
    ("client_name", "客户"),
    ("task_type", "任务类型"),
    ("progress_content", "工作进展"),
    ("result_content", "工作成果"),
    ("duration_minutes", "耗时（分钟）"),
    ("source_label", "来源"),
)


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def _display_user(user: AppUser) -> str:
    return (user.full_name or user.username or "").strip()


def _valid_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return validate_email(value, check_deliverability=False).normalized
    except EmailNotValidError:
        return None


def _account(db: Session, user_id: UUID) -> Optional[UserMailAccount]:
    return db.query(UserMailAccount).filter(UserMailAccount.user_id == user_id).first()


def serialize_mail_account(db: Session, user: AppUser) -> dict:
    account = _account(db, user.id)
    current_email = _valid_email(user.email)
    email_matches = bool(account and current_email and account.email_snapshot.casefold() == current_email.casefold())
    return {
        "email": current_email,
        "is_bound": bool(account),
        "is_verified": bool(account and account.is_verified and email_matches),
        "verified_at": account.verified_at if account else None,
        "updated_at": account.updated_at if account else None,
    }


def save_mail_account(db: Session, user: AppUser, authorization_code: str) -> dict:
    email = _valid_email(user.email)
    if not email:
        raise ValueError("当前用户尚未绑定有效企业邮箱，请联系管理员完善用户邮箱")
    code = authorization_code.strip()
    if not code:
        raise ValueError("邮箱授权码不能为空")
    ciphertext, version = encrypt_credential(code)
    account = _account(db, user.id)
    if not account:
        account = UserMailAccount(user_id=user.id, email_snapshot=email, authorization_ciphertext=ciphertext, encryption_key_version=version)
        db.add(account)
    else:
        account.email_snapshot = email
        account.authorization_ciphertext = ciphertext
        account.encryption_key_version = version
    account.is_verified = False
    account.verified_at = None
    account.updated_at = _now()
    db.commit()
    return serialize_mail_account(db, user)


def delete_mail_account(db: Session, user: AppUser) -> None:
    account = _account(db, user.id)
    if account:
        db.delete(account)
        db.commit()


def _personal_smtp_settings(db: Session, user: AppUser, *, require_verified: bool = True) -> SmtpSettings:
    email = _valid_email(user.email)
    if not email:
        raise MailConfigurationError("当前用户没有有效企业邮箱")
    account = _account(db, user.id)
    if not account:
        raise MailConfigurationError("尚未绑定个人邮箱授权码")
    if account.email_snapshot.casefold() != email.casefold():
        raise MailConfigurationError("用户邮箱已变更，请重新绑定个人邮箱授权码")
    if require_verified and not account.is_verified:
        raise MailConfigurationError("个人邮箱授权尚未验证")
    authorization_code = decrypt_credential(account.authorization_ciphertext, account.encryption_key_version)
    base = SmtpSettings.from_env()
    return replace(
        base,
        username=email,
        password=authorization_code,
        sender_email=email,
        sender_name=_display_user(user),
        reply_to=email,
    )


def verify_mail_account(db: Session, user: AppUser) -> dict:
    settings = _personal_smtp_settings(db, user, require_verified=False)
    verify_smtp_settings(settings)
    account = _account(db, user.id)
    account.is_verified = True
    account.verified_at = _now()
    account.updated_at = account.verified_at
    db.commit()
    return serialize_mail_account(db, user)


def _policy(db: Session, user_id: UUID) -> Optional[DailyReportMailPolicy]:
    return (
        db.query(DailyReportMailPolicy)
        .options(
            joinedload(DailyReportMailPolicy.groups)
            .joinedload(DailyReportMailPolicyGroup.group)
            .joinedload(MailRecipientGroup.members)
            .joinedload(MailRecipientGroupMember.user)
        )
        .filter(DailyReportMailPolicy.user_id == user_id)
        .first()
    )


def _serialize_policy(db: Session, user: AppUser) -> dict:
    policy = _policy(db, user.id)
    links = list(policy.groups) if policy else []
    account = _account(db, user.id)
    return {
        "user_id": user.id,
        "user_name": _display_user(user),
        "email": _valid_email(user.email),
        "is_active": bool(user.is_active),
        "mail_account_bound": bool(account),
        "mail_account_verified": bool(
            account and account.is_verified and _valid_email(user.email)
            and account.email_snapshot.casefold() == _valid_email(user.email).casefold()
        ),
        "to_group_ids": [item.group_id for item in links if item.recipient_type == "to"],
        "cc_group_ids": [item.group_id for item in links if item.recipient_type == "cc"],
    }


def list_daily_report_policies(db: Session) -> list[dict]:
    users = db.query(AppUser).order_by(AppUser.full_name, AppUser.username).all()
    return [_serialize_policy(db, user) for user in users]


def save_daily_report_policy(db: Session, user_id: UUID, payload, actor_id: UUID) -> dict:
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise LookupError("用户不存在")
    to_ids = list(dict.fromkeys(payload.to_group_ids))
    to_set = set(to_ids)
    cc_ids = [item for item in dict.fromkeys(payload.cc_group_ids) if item not in to_set]
    if not to_ids:
        raise ValueError("至少需要配置一个工作报告主送组")
    all_ids = [*to_ids, *cc_ids]
    groups = db.query(MailRecipientGroup).filter(MailRecipientGroup.id.in_(all_ids)).all()
    group_by_id = {item.id: item for item in groups}
    invalid = [str(item) for item in all_ids if item not in group_by_id or not group_by_id[item].is_active]
    if invalid:
        raise ValueError(f"邮件组不存在或已停用：{', '.join(invalid)}")
    policy = db.query(DailyReportMailPolicy).filter(DailyReportMailPolicy.user_id == user_id).first()
    if not policy:
        policy = DailyReportMailPolicy(user_id=user_id)
        db.add(policy)
        db.flush()
    policy.updated_by = actor_id
    policy.updated_at = _now()
    policy.groups.clear()
    db.flush()
    policy.groups = [
        DailyReportMailPolicyGroup(user_id=user_id, group_id=group_id, recipient_type=kind)
        for kind, ids in (("to", to_ids), ("cc", cc_ids))
        for group_id in ids
    ]
    db.commit()
    return _serialize_policy(db, user)


def _recipient_view(user: AppUser, recipient_type: str) -> dict:
    return {
        "user_id": user.id,
        "display_name": _display_user(user),
        "email": _valid_email(user.email),
        "recipient_type": recipient_type,
    }


def _policy_recipients(db: Session, user_id: UUID) -> tuple[list[AppUser], list[AppUser]]:
    policy = _policy(db, user_id)
    if not policy:
        raise ValueError("尚未配置工作报告收件策略")
    ordered: dict[str, list[AppUser]] = {"to": [], "cc": []}
    seen_ids: dict[str, set[UUID]] = {"to": set(), "cc": set()}
    for link in policy.groups:
        if not link.group or not link.group.is_active:
            raise ValueError("工作报告收件组已停用，请管理员修复邮件设置")
        for member in link.group.members:
            recipient = member.user
            if not recipient or not recipient.is_active or not _valid_email(recipient.email):
                label = _display_user(recipient) if recipient else str(member.user_id)
                raise ValueError(f"收件组成员“{label}”已停用或缺少有效邮箱")
            if recipient.id not in seen_ids[link.recipient_type]:
                seen_ids[link.recipient_type].add(recipient.id)
                ordered[link.recipient_type].append(recipient)
    to_users = ordered["to"]
    to_emails = {_valid_email(item.email).casefold() for item in to_users}
    cc_users = [item for item in ordered["cc"] if _valid_email(item.email).casefold() not in to_emails]
    if not to_users:
        raise ValueError("工作报告主送组中没有可用收件人")
    return to_users, cc_users


def _finalized_report(db: Session, user_id: UUID, report_date: datetime.date) -> DailyReport:
    report = (
        db.query(DailyReport)
        .options(joinedload(DailyReport.items), joinedload(DailyReport.user))
        .filter(DailyReport.user_id == user_id, DailyReport.report_date == report_date)
        .first()
    )
    if not report or report.status != "finalized":
        raise ValueError("请先确认日报再发送邮箱")
    return report


def _report_rows(report: DailyReport) -> list[dict]:
    rows = []
    for item in sorted(report.items, key=lambda value: value.sort_order):
        metadata = item.display_metadata or {}
        rows.append({
            "order_no": str(metadata.get("order_no") or ""),
            "task_name": item.task_name or "",
            "client_name": str(metadata.get("client_short_name") or ""),
            "task_type": item.task_type or "",
            "progress_content": item.progress_content or "",
            "result_content": item.result_content or "",
            "duration_minutes": int(item.duration_minutes or 0),
            "source_label": SOURCE_LABELS.get(item.source_type, item.source_type),
        })
    return rows


def build_daily_report_mail_preview(db: Session, user: AppUser, report_date: datetime.date) -> dict:
    report = _finalized_report(db, user.id, report_date)
    reasons: list[str] = []
    account_status = serialize_mail_account(db, user)
    if not account_status["email"]:
        reasons.append("当前用户缺少有效企业邮箱")
    elif not account_status["is_bound"]:
        reasons.append("尚未绑定个人邮箱授权码")
    elif not account_status["is_verified"]:
        reasons.append("个人邮箱授权尚未验证")
    try:
        to_users, cc_users = _policy_recipients(db, user.id)
    except ValueError as exc:
        to_users, cc_users = [], []
        reasons.append(str(exc))
    status = get_mail_status()
    if not status.get("configured"):
        reasons.append(status.get("detail") or "SMTP 服务尚未配置")
    return {
        "report_id": report.id,
        "report_date": report.report_date.isoformat(),
        "sender_name": _display_user(user),
        "sender_email": account_status["email"],
        "subject": f"{report.report_date:%Y年%m月%d日}{_display_user(user)}工作报告",
        "rows": _report_rows(report),
        "supplemental_note": report.supplemental_note,
        "to_users": [_recipient_view(item, "to") for item in to_users],
        "cc_users": [_recipient_view(item, "cc") for item in cc_users],
        "can_send": not reasons,
        "blocking_reasons": reasons,
        "delivery_mode": status.get("mode") or "disabled",
        "test_recipient_masked": status.get("test_recipient_masked"),
    }


def render_daily_report_mail(rows: list[dict], supplemental_note: Optional[str]) -> tuple[str, str]:
    header_html = "".join(
        f'<th style="border:1px solid #9ca3af;background:#dbeafe;color:#1e3a5f;padding:7px 9px;text-align:center;font-weight:700;">{html.escape(label)}</th>'
        for _, label in MAIL_COLUMNS
    )
    body_rows = []
    plain_lines = ["\t".join(label for _, label in MAIL_COLUMNS)]
    for row in rows:
        cells = []
        plain_values = []
        for key, _label in MAIL_COLUMNS:
            value = str(row.get(key, "") if row.get(key, "") is not None else "")
            plain_values.append(value.replace("\t", " ").replace("\r", " ").replace("\n", " / "))
            cells.append(
                '<td style="border:1px solid #9ca3af;padding:7px 9px;vertical-align:top;white-space:pre-wrap;word-break:break-word;">'
                f"{html.escape(value)}"
                "</td>"
            )
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
        plain_lines.append("\t".join(plain_values))
    total_minutes = sum(max(0, int(row.get("duration_minutes") or 0)) for row in rows)
    total_hours = f"{total_minutes / 60:.2f}".rstrip("0").rstrip(".")
    total_text = f"{total_hours} 小时（{total_minutes} 分钟）"
    body_rows.append(
        '<tr style="background:#ecfdf5;color:#166534;font-weight:700;">'
        '<td colspan="7" style="border:1px solid #9ca3af;padding:7px 9px;text-align:right;">当日工作耗时合计</td>'
        f'<td style="border:1px solid #9ca3af;padding:7px 9px;text-align:center;">{html.escape(total_text)}</td>'
        '<td style="border:1px solid #9ca3af;padding:7px 9px;"></td>'
        '</tr>'
    )
    plain_lines.append(f"当日工作耗时合计\t{total_text}")
    note_html = ""
    if supplemental_note:
        escaped_note = html.escape(supplemental_note)
        note_html = (
            '<table role="presentation" style="border-collapse:collapse;width:100%;margin-top:12px;font-family:Microsoft YaHei,Arial,sans-serif;font-size:13px;">'
            '<tr><th style="width:100px;border:1px solid #9ca3af;background:#f1f5f9;padding:7px 9px;text-align:left;">补充说明</th>'
            f'<td style="border:1px solid #9ca3af;padding:7px 9px;white-space:pre-wrap;word-break:break-word;">{escaped_note}</td></tr></table>'
        )
        plain_lines.extend(["", f"补充说明：{supplemental_note}"])
    html_body = (
        '<div style="font-family:Microsoft YaHei,Arial,sans-serif;color:#1f2937;font-size:13px;">'
        '<table role="presentation" style="border-collapse:collapse;width:100%;table-layout:auto;">'
        f"<thead><tr>{header_html}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>{note_html}</div>"
    )
    return html_body, "\n".join(plain_lines)


def _delivery(db: Session, delivery_id: UUID) -> Optional[DailyReportMailDelivery]:
    return (
        db.query(DailyReportMailDelivery)
        .options(joinedload(DailyReportMailDelivery.recipients))
        .filter(DailyReportMailDelivery.id == delivery_id)
        .first()
    )


def serialize_delivery(delivery: DailyReportMailDelivery) -> dict:
    return {
        "id": delivery.id,
        "report_id": delivery.report_id,
        "sender_name": delivery.sender_name_snapshot,
        "sender_email": delivery.sender_email_snapshot,
        "subject": delivery.subject,
        "rows": delivery.body_rows,
        "supplemental_note": delivery.supplemental_note,
        "recipients": [
            {
                "user_id": item.user_id,
                "display_name": item.display_name_snapshot,
                "email": item.email_snapshot,
                "recipient_type": item.recipient_type,
            }
            for item in delivery.recipients
        ],
        "status": delivery.status,
        "delivery_mode": delivery.delivery_mode,
        "send_error": delivery.send_error,
        "created_at": delivery.created_at,
        "send_attempted_at": delivery.send_attempted_at,
        "sent_at": delivery.sent_at,
    }


def send_daily_report_mail(db: Session, user: AppUser, report_date: datetime.date, payload) -> DailyReportMailDelivery:
    duplicate = db.query(DailyReportMailDelivery).filter(
        DailyReportMailDelivery.idempotency_key == payload.idempotency_key
    ).first()
    if duplicate:
        return _delivery(db, duplicate.id)
    report = _finalized_report(db, user.id, report_date)
    if len(payload.rows) != len(report.items):
        raise ValueError("邮件表格行数与已确认日报不一致，请重新打开预览")
    settings = _personal_smtp_settings(db, user)
    to_users, cc_users = _policy_recipients(db, user.id)
    rows = [item.model_dump() for item in payload.rows]
    body_html, body_text = render_daily_report_mail(rows, payload.supplemental_note)
    message_id = f"<daily-report-{payload.idempotency_key}@xinshi-system.local>"
    delivery = DailyReportMailDelivery(
        report_id=report.id,
        user_id=user.id,
        sender_name_snapshot=_display_user(user),
        sender_email_snapshot=_valid_email(user.email),
        subject=payload.subject,
        body_rows=rows,
        supplemental_note=payload.supplemental_note,
        body_html=body_html,
        body_text=body_text,
        idempotency_key=payload.idempotency_key,
        smtp_message_id=message_id,
        status="pending",
    )
    db.add(delivery)
    db.flush()
    for kind, recipients in (("to", to_users), ("cc", cc_users)):
        for recipient in recipients:
            delivery.recipients.append(DailyReportMailRecipient(
                user_id=recipient.id,
                recipient_type=kind,
                display_name_snapshot=_display_user(recipient),
                email_snapshot=_valid_email(recipient.email),
            ))
    delivery.status = "sending"
    delivery.send_attempted_at = _now()
    db.commit()
    attempt = DailyReportMailAttempt(delivery_id=delivery.id)
    db.add(attempt)
    try:
        result = send_text_email(
            to_emails=[_valid_email(item.email) for item in to_users],
            cc_emails=[_valid_email(item.email) for item in cc_users],
            subject=payload.subject,
            body=body_text,
            html_body=body_html,
            message_id=message_id,
            settings=settings,
        )
        delivery.status = "sent"
        delivery.delivery_mode = result.delivery_mode
        delivery.sent_at = _now()
        delivery.send_error = None
        attempt.delivery_mode = result.delivery_mode
        attempt.actual_recipients = result.delivery_recipient
        attempt.success = True
    except (MailConfigurationError, MailDeliveryError) as exc:
        delivery.status = "failed"
        delivery.delivery_mode = settings.mode
        delivery.send_error = str(exc)
        attempt.delivery_mode = settings.mode
        attempt.error = str(exc)
        attempt.success = False
    db.commit()
    return _delivery(db, delivery.id)


def list_daily_report_deliveries(db: Session, user_id: UUID, report_date: datetime.date) -> list[DailyReportMailDelivery]:
    report = db.query(DailyReport).filter(
        DailyReport.user_id == user_id, DailyReport.report_date == report_date
    ).first()
    if not report:
        return []
    return (
        db.query(DailyReportMailDelivery)
        .options(joinedload(DailyReportMailDelivery.recipients))
        .filter(DailyReportMailDelivery.report_id == report.id)
        .order_by(DailyReportMailDelivery.created_at.desc())
        .all()
    )
