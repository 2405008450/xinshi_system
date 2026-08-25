"""项目邮件与稿件安排共用的 SMTP 邮件发送服务。"""
from __future__ import annotations

import os
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


def get_mail_status() -> dict:
    """返回不包含密码的邮件配置状态。"""
    try:
        settings = SmtpSettings.from_env()
        settings.validate()
        return {
            "mode": settings.mode,
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


def send_text_email(
    *,
    to_emails: Iterable[str],
    cc_emails: Iterable[str] = (),
    subject: Optional[str],
    body: Optional[str],
    message_id: str,
    settings: Optional[SmtpSettings] = None,
) -> MailSendResult:
    """通过 SMTP 发送支持 To/CC 的 UTF-8 纯文本邮件。

    test 模式会强制覆盖全部收件人，避免联调期间误发给真实用户。
    """
    config = settings or SmtpSettings.from_env()
    config.validate()

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
    message.set_content(body or "", subtype="plain", charset="utf-8")

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


def send_plain_text_email(
    *,
    recipient_email: Optional[str],
    subject: Optional[str],
    body: Optional[str],
    message_id: str,
    settings: Optional[SmtpSettings] = None,
) -> MailSendResult:
    """兼容稿件安排的单收件人调用。"""
    return send_text_email(
        to_emails=[recipient_email] if recipient_email else [],
        subject=subject,
        body=body,
        message_id=message_id,
        settings=settings,
    )
