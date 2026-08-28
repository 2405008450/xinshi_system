from uuid import uuid4

import pytest
from pydantic import ValidationError

import mail_service
from daily_report_mail_schemas import DailyReportMailSendRequest
from daily_report_mail_service import render_daily_report_mail
from mail_service import SmtpSettings, send_text_email, verify_smtp_settings


class _FakeSmtp:
    last_message = None
    login_args = None
    noop_called = False

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

    def login(self, *args):
        type(self).login_args = args

    def noop(self):
        type(self).noop_called = True

    def send_message(self, message):
        type(self).last_message = message


def _settings():
    return SmtpSettings(
        mode="test",
        host="smtp.mxhichina.com",
        port=465,
        security="ssl",
        username="zhangsan@example.com",
        password="authorization-code",
        sender_email="zhangsan@example.com",
        sender_name="张三",
        reply_to="zhangsan@example.com",
        timeout_seconds=5,
        test_recipient="safe@example.com",
    )


def test_daily_report_html_escapes_user_content_and_preserves_table():
    html_body, plain_body = render_daily_report_mail([{
        "order_no": "TP-001",
        "task_name": "客户 <项目>",
        "client_name": "客户A",
        "task_type": "翻译",
        "progress_content": "完成 50%\n等待反馈",
        "result_content": "<script>alert(1)</script>",
        "duration_minutes": 60,
        "source_label": "项目任务",
    }], "补充 <说明>")

    assert "<table" in html_body
    assert "客户 &lt;项目&gt;" in html_body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_body
    assert "<script>" not in html_body
    assert "补充 &lt;说明&gt;" in html_body
    assert "当日工作耗时合计" in html_body
    assert "1 小时（60 分钟）" in html_body
    assert "当日工作耗时合计\t1 小时（60 分钟）" in plain_body
    assert "TP-001" in plain_body


def test_daily_report_payload_rejects_subject_header_injection():
    with pytest.raises(ValidationError):
        DailyReportMailSendRequest(
            subject="2026年08月28日张三工作报告\nBcc: outsider@example.com",
            rows=[],
            idempotency_key=f"daily-report-{uuid4()}",
        )


def test_personal_smtp_builds_html_alternative_and_uses_test_recipient(monkeypatch):
    monkeypatch.setattr(mail_service.smtplib, "SMTP_SSL", _FakeSmtp)
    result = send_text_email(
        to_emails=["manager@example.com"],
        subject="2026年08月28日张三工作报告",
        body="纯文本日报",
        html_body="<table><tr><td>日报</td></tr></table>",
        message_id="<daily-report-test@xinshi-system.local>",
        settings=_settings(),
    )

    assert result.delivery_recipient == "safe@example.com"
    assert _FakeSmtp.login_args == ("zhangsan@example.com", "authorization-code")
    assert _FakeSmtp.last_message["From"] == "张三 <zhangsan@example.com>"
    assert _FakeSmtp.last_message["To"] == "safe@example.com"
    assert _FakeSmtp.last_message.get_body(preferencelist=("html",)).get_content_type() == "text/html"


def test_personal_smtp_verification_does_not_send_mail(monkeypatch):
    _FakeSmtp.last_message = None
    _FakeSmtp.noop_called = False
    monkeypatch.setattr(mail_service.smtplib, "SMTP_SSL", _FakeSmtp)

    verify_smtp_settings(_settings())

    assert _FakeSmtp.noop_called is True
    assert _FakeSmtp.last_message is None
