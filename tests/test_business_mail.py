from uuid import uuid4

import pytest
from pydantic import ValidationError

import mail_service
from business_mail_schemas import BusinessMailSendRequest, MailRecipientGroupWrite
from mail_service import SmtpSettings, send_text_email


class _FakeSmtp:
    last_message = None

    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def ehlo(self):
        pass

    def starttls(self, **_kwargs):
        pass

    def login(self, *_args):
        pass

    def send_message(self, message):
        type(self).last_message = message


def _settings(mode="test"):
    return SmtpSettings(
        mode=mode,
        host="smtp.example.com",
        port=25,
        security="none",
        username="",
        password="",
        sender_email="system@example.com",
        sender_name="信实系统",
        reply_to="",
        timeout_seconds=5,
        test_recipient="safe@example.com",
    )


def test_test_mode_overrides_all_business_recipients(monkeypatch):
    monkeypatch.setattr(mail_service.smtplib, "SMTP", _FakeSmtp)

    result = send_text_email(
        to_emails=["employee1@example.com"],
        cc_emails=["employee2@example.com"],
        subject="新项目",
        body="项目内容",
        message_id="<test@xinshi-system.local>",
        settings=_settings(),
    )

    assert result.delivery_recipient == "safe@example.com"
    assert _FakeSmtp.last_message["To"] == "safe@example.com"
    assert _FakeSmtp.last_message["Cc"] is None
    assert _FakeSmtp.last_message["Subject"] == "[测试发送] 新项目"


def test_business_mail_payload_rejects_header_injection():
    with pytest.raises(ValidationError):
        BusinessMailSendRequest(
            project_type="translation",
            project_id=uuid4(),
            source_kind="project_manual",
            to_user_ids=[uuid4()],
            subject="正常主题\nBcc: outsider@example.com",
            body="项目内容",
            idempotency_key="mail-test-001",
        )


def test_recipient_group_requires_name_and_internal_members():
    with pytest.raises(ValidationError):
        MailRecipientGroupWrite(name="   ", user_ids=[])

