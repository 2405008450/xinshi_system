"""项目邮件与稿件安排共用的 SMTP 邮件发送服务。"""
from __future__ import annotations

import base64
import os
import re
import smtplib
import socket
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from typing import Iterable, Optional

from email_validator import EmailNotValidError, validate_email


class MailConfigurationError(RuntimeError):
    """邮件服务配置不完整或不合法。"""


class MailDeliveryError(RuntimeError):
    """SMTP 已配置，但邮件投递失败。"""


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _validated_email(value: str, field_name: str) -> str:
    try:
        return validate_email(value, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise MailConfigurationError(f"{field_name}不是有效邮箱地址") from exc


def mask_email(value: Optional[str]) -> Optional[str]:
    """只向前端暴露脱敏后的测试邮箱。"""
    if not value or "@" not in value:
        return None
    local, domain = value.rsplit("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}***@{domain}"


@dataclass(frozen=True)
class SmtpSettings:
    mode: str
    host: str
    port: int
    security: str
    username: str
    password: str
    sender_email: str
    sender_name: str
    reply_to: str
    timeout_seconds: float
    test_recipient: str

    @classmethod
    def from_env(cls) -> "SmtpSettings":
        mode = _env("SMTP_MODE", "disabled").lower()
        security = _env("SMTP_SECURITY", "starttls").lower()
        try:
            port = int(_env("SMTP_PORT", "587"))
            timeout_seconds = float(_env("SMTP_TIMEOUT_SECONDS", "15"))
        except ValueError as exc:
            raise MailConfigurationError("SMTP 端口或超时时间配置不合法") from exc

        return cls(
            mode=mode,
            host=_env("SMTP_HOST"),
            port=port,
            security=security,
            username=_env("SMTP_USERNAME"),
            password=os.getenv("SMTP_PASSWORD", ""),
            sender_email=_env("SMTP_FROM_EMAIL"),
            sender_name=_env("SMTP_FROM_NAME", "信实翻译"),
            reply_to=_env("SMTP_REPLY_TO"),
            timeout_seconds=timeout_seconds,
            test_recipient=_env("SMTP_TEST_RECIPIENT"),
        )

    def validate(self) -> None:
        if self.mode not in {"disabled", "test", "live"}:
            raise MailConfigurationError("SMTP_MODE 只能是 disabled、test 或 live")
        if self.mode == "disabled":
            raise MailConfigurationError("邮件发送尚未启用，请配置 SMTP_MODE")
        if not self.host:
            raise MailConfigurationError("缺少 SMTP_HOST")
        if not 1 <= self.port <= 65535:
            raise MailConfigurationError("SMTP_PORT 必须在 1-65535 之间")
        if self.security not in {"none", "starttls", "ssl"}:
            raise MailConfigurationError("SMTP_SECURITY 只能是 none、starttls 或 ssl")
        if self.timeout_seconds <= 0:
            raise MailConfigurationError("SMTP_TIMEOUT_SECONDS 必须大于 0")
        _validated_email(self.sender_email, "SMTP_FROM_EMAIL")
        if self.reply_to:
            _validated_email(self.reply_to, "SMTP_REPLY_TO")
        if self.username and not self.password:
            raise MailConfigurationError("配置 SMTP_USERNAME 时必须同时配置 SMTP_PASSWORD")
        if self.mode == "test":
            if not self.test_recipient:
                raise MailConfigurationError("测试模式必须配置 SMTP_TEST_RECIPIENT")
            _validated_email(self.test_recipient, "SMTP_TEST_RECIPIENT")


@dataclass(frozen=True)
class MailSendResult:
    delivery_recipient: str
    message_id: str
    delivery_mode: str


@dataclass(frozen=True)
class MailAttachment:
    """邮件附件；内容仅在本次请求内存中使用，不负责持久化。"""

    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


@dataclass(frozen=True)
class MailInlineImagePart:
    """发送前将 CID 引用转换为 HTML Data URI 的正文图片。"""

    cid: str
    filename: str
    content: bytes
    content_type: str


def get_mail_status() -> dict:
    """返回不包含密码的邮件配置状态。"""
    project_sender_mode = _env("PROJECT_MAIL_SENDER_MODE", "system").lower()
    try:
        settings = SmtpSettings.from_env()
        settings.validate()
        return {
            "mode": settings.mode,
            "project_sender_mode": project_sender_mode,
            "configured": True,
            "host": settings.host,
            "port": settings.port,
            "security": settings.security,
            "sender_email": settings.sender_email,
            "test_recipient_masked": mask_email(settings.test_recipient),
            "detail": "测试模式：邮件只发送到测试收件箱"
            if settings.mode == "test"
            else "正式模式：邮件发送到业务指定收件人",
        }
    except MailConfigurationError as exc:
        mode = _env("SMTP_MODE", "disabled").lower()
        return {
            "mode": mode,
            "project_sender_mode": project_sender_mode,
            "configured": False,
            "host": _env("SMTP_HOST") or None,
            "port": None,
            "security": _env("SMTP_SECURITY", "starttls").lower(),
            "sender_email": _env("SMTP_FROM_EMAIL") or None,
            "test_recipient_masked": mask_email(_env("SMTP_TEST_RECIPIENT")),
            "detail": str(exc),
        }


def _normalized_recipients(values: Iterable[str], field_name: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _validated_email(value, field_name)
        key = normalized.lower()
        if key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def _embed_inline_images_as_data_uris(
    html_body: str,
    inline_images: Iterable[MailInlineImagePart],
) -> str:
    rendered_html = html_body
    for image in inline_images:
        content_type = (image.content_type or "").partition(";")[0].strip().lower()
        maintype, _, subtype = content_type.partition("/")
        if maintype != "image" or not subtype:
            raise MailConfigurationError("正文内嵌资源必须是有效图片")
        cid = image.cid.strip("<>")
        data_uri = f"data:{content_type};base64,{base64.b64encode(image.content).decode('ascii')}"
        rendered_html, replacement_count = re.subn(
            rf"cid:{re.escape(cid)}",
            data_uri,
            rendered_html,
            flags=re.IGNORECASE,
        )
        if replacement_count == 0:
            raise MailConfigurationError(f"HTML 正文未引用内嵌图片：{image.filename}")
    return rendered_html


def send_text_email(
    *,
    to_emails: Iterable[str],
    cc_emails: Iterable[str] = (),
    subject: Optional[str],
    body: Optional[str],
    html_body: Optional[str] = None,
    attachments: Iterable[MailAttachment] = (),
    inline_images: Iterable[MailInlineImagePart] = (),
    message_id: str,
    settings: Optional[SmtpSettings] = None,
) -> MailSendResult:
    """通过 SMTP 发送支持 To/CC 的 UTF-8 纯文本邮件。

    test 模式会强制覆盖全部收件人，避免联调期间误发给真实用户。
    """
    config = settings or SmtpSettings.from_env()
    config.validate()
    normalized_attachments = list(attachments)
    normalized_inline_images = list(inline_images)
    if normalized_inline_images and not html_body:
        raise MailConfigurationError("邮件包含正文图片时必须同时提供 HTML 正文")

    if config.mode == "test":
        delivery_to = [_validated_email(
            config.test_recipient,
            "SMTP_TEST_RECIPIENT",
        )]
        delivery_cc: list[str] = []
    else:
        delivery_to = _normalized_recipients(to_emails, "收件邮箱")
        delivery_cc = _normalized_recipients(cc_emails, "抄送邮箱")
        to_keys = {item.lower() for item in delivery_to}
        delivery_cc = [item for item in delivery_cc if item.lower() not in to_keys]
        if not delivery_to:
            raise MailConfigurationError("至少需要一个有效的收件邮箱")

    sender_email = _validated_email(config.sender_email, "SMTP_FROM_EMAIL")
    normalized_reply_to = (
        _validated_email(config.reply_to, "SMTP_REPLY_TO")
        if config.reply_to
        else None
    )

    message = EmailMessage()
    message["From"] = formataddr((config.sender_name, sender_email))
    message["To"] = ", ".join(delivery_to)
    if delivery_cc:
        message["Cc"] = ", ".join(delivery_cc)
    message["Subject"] = (
        f"[测试发送] {subject or '稿件安排'}"
        if config.mode == "test"
        else subject or "稿件安排"
    )
    message["Message-ID"] = message_id
    if normalized_reply_to:
        message["Reply-To"] = normalized_reply_to
    rendered_html = (
        _embed_inline_images_as_data_uris(html_body, normalized_inline_images)
        if normalized_inline_images
        else html_body
    )
    message.set_content(body or "", subtype="plain", charset="utf-8")
    if rendered_html:
        message.add_alternative(rendered_html, subtype="html", charset="utf-8")
    for attachment in normalized_attachments:
        content_type = (attachment.content_type or "").partition(";")[0].strip().lower()
        if "/" in content_type:
            maintype, subtype = content_type.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"
        if not maintype or not subtype:
            maintype, subtype = "application", "octet-stream"
        message.add_attachment(
            attachment.content,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.filename,
        )

    context = ssl.create_default_context()
    try:
        if config.security == "ssl":
            smtp_client = smtplib.SMTP_SSL(
                config.host,
                config.port,
                timeout=config.timeout_seconds,
                context=context,
            )
        else:
            smtp_client = smtplib.SMTP(
                config.host,
                config.port,
                timeout=config.timeout_seconds,
            )

        with smtp_client as client:
            client.ehlo()
            if config.security == "starttls":
                client.starttls(context=context)
                client.ehlo()
            if config.username:
                client.login(config.username, config.password)
            client.send_message(message)
    except (smtplib.SMTPException, OSError, socket.timeout) as exc:
        raise MailDeliveryError(f"SMTP 投递失败：{exc}") from exc

    return MailSendResult(
        delivery_recipient=", ".join([*delivery_to, *delivery_cc]),
        message_id=message_id,
        delivery_mode=config.mode,
    )


def verify_smtp_settings(settings: SmtpSettings) -> None:
    """仅验证 SMTP 连接与授权，不发送邮件。"""
    settings.validate()
    context = ssl.create_default_context()
    try:
        if settings.security == "ssl":
            smtp_client = smtplib.SMTP_SSL(
                settings.host,
                settings.port,
                timeout=settings.timeout_seconds,
                context=context,
            )
        else:
            smtp_client = smtplib.SMTP(
                settings.host,
                settings.port,
                timeout=settings.timeout_seconds,
            )
        with smtp_client as client:
            client.ehlo()
            if settings.security == "starttls":
                client.starttls(context=context)
                client.ehlo()
            if settings.username:
                client.login(settings.username, settings.password)
            client.noop()
    except (smtplib.SMTPException, OSError, socket.timeout) as exc:
        raise MailDeliveryError(f"SMTP 授权验证失败：{exc}") from exc


def send_plain_text_email(
    *,
    recipient_email: Optional[str],
    cc_emails: Iterable[str] = (),
    subject: Optional[str],
    body: Optional[str],
    attachment: Optional[MailAttachment] = None,
    attachments: Iterable[MailAttachment] = (),
    html_body: Optional[str] = None,
    inline_images: Iterable[MailInlineImagePart] = (),
    message_id: str,
    settings: Optional[SmtpSettings] = None,
) -> MailSendResult:
    """兼容稿件安排的单收件人调用。"""
    normalized_attachments = list(attachments)
    if attachment:
        normalized_attachments.insert(0, attachment)
    return send_text_email(
        to_emails=[recipient_email] if recipient_email else [],
        cc_emails=cc_emails,
        subject=subject,
        body=body,
        html_body=html_body,
        attachments=normalized_attachments,
        inline_images=inline_images,
        message_id=message_id,
        settings=settings,
    )
