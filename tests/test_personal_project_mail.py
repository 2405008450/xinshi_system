from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import business_mail_service
import user_mail_account_service
from business_mail_models import BusinessMail, BusinessMailAttempt
from business_mail_service import _deliver, build_preview, serialize_mail
from mail_service import (
    MailConfigurationError,
    MailDeliveryError,
    MailSendResult,
    SmtpSettings,
)
from user_mail_account_service import (
    personal_smtp_settings,
    resolve_project_sender,
    serialize_mail_account,
)


def _settings() -> SmtpSettings:
    return SmtpSettings(
        mode="test",
        host="smtp.example.com",
        port=465,
        security="ssl",
        username="fixed@example.com",
        password="fixed-secret",
        sender_email="fixed@example.com",
        sender_name="固定发件箱",
        reply_to="fixed@example.com",
        timeout_seconds=5,
        test_recipient="safe@example.com",
    )


class _AccountQuery:
    def __init__(self, account):
        self.account = account

    def filter(self, *_args):
        return self

    def first(self):
        return self.account


class _AccountDb:
    def __init__(self, account=None):
        self.account = account

    def query(self, _model):
        return _AccountQuery(self.account)


def _user(email="user@example.com", name="当前用户"):
    return SimpleNamespace(id=uuid4(), email=email, full_name=name, username="user")


def _account(email="user@example.com", verified=True):
    return SimpleNamespace(
        email_snapshot=email,
        authorization_ciphertext=b"encrypted",
        encryption_key_version="v1",
        is_verified=verified,
        verified_at=datetime(2026, 8, 30, 10, 0),
        updated_at=datetime(2026, 8, 30, 10, 0),
    )


def test_personal_smtp_replaces_only_sender_credentials(monkeypatch):
    user = _user()
    db = _AccountDb(_account())
    monkeypatch.setattr(user_mail_account_service, "decrypt_credential", lambda *_args: "personal-secret")
    monkeypatch.setattr(user_mail_account_service.SmtpSettings, "from_env", _settings)

    settings = personal_smtp_settings(db, user)

    assert settings.host == "smtp.example.com"
    assert settings.port == 465
    assert settings.username == "user@example.com"
    assert settings.password == "personal-secret"
    assert settings.sender_email == "user@example.com"
    assert settings.sender_name == "当前用户"
    assert settings.reply_to == "user@example.com"


def test_changed_admin_email_invalidates_existing_binding(monkeypatch):
    user = _user(email="new@example.com")
    db = _AccountDb(_account(email="old@example.com"))
    status = serialize_mail_account(db, user)

    assert status["is_bound"] is True
    assert status["is_verified"] is False
    with pytest.raises(MailConfigurationError, match="邮箱已变更"):
        personal_smtp_settings(db, user)


def test_project_sender_mode_keeps_system_account_compatible(monkeypatch):
    monkeypatch.setenv("PROJECT_MAIL_SENDER_MODE", "system")
    monkeypatch.setattr(user_mail_account_service.SmtpSettings, "from_env", _settings)

    settings, sender = resolve_project_sender(_AccountDb(), _user())

    assert settings.username == "fixed@example.com"
    assert sender == {
        "sender_mode": "system",
        "sender_name": "固定发件箱",
        "sender_email": "fixed@example.com",
        "sender_verified": True,
    }


def test_personal_preview_blocks_unavailable_current_sender(monkeypatch):
    monkeypatch.setattr(business_mail_service, "policy_recipients", lambda *_args: ([], []))
    monkeypatch.setattr(business_mail_service, "get_user_mail_profile", lambda *_args: None)
    monkeypatch.setattr(business_mail_service, "project_mail_sender_mode", lambda: "personal")
    monkeypatch.setattr(
        business_mail_service,
        "resolve_project_sender",
        lambda *_args: (_ for _ in ()).throw(MailConfigurationError("尚未绑定个人邮箱 SMTP 凭据")),
    )
    user = _user()

    preview = build_preview(
        object(),
        "translation",
        current_user=user,
        source={
            "order_no": "TP-260830-001",
            "project_name": "测试项目",
            "service_content": "笔译",
            "language_pair": "中英",
            "customer_deadline_time": "2026-09-01 12:00",
        },
    )

    assert preview["sender_mode"] == "personal"
    assert preview["sender_email"] == "user@example.com"
    assert preview["sender_verified"] is False
    assert preview["can_send"] is False
    assert "尚未绑定个人邮箱" in "；".join(preview["blocking_reasons"])


class _MailQuery:
    def __init__(self, mail):
        self.mail = mail

    def options(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def first(self):
        return self.mail


class _MailDb:
    def __init__(self, mail):
        self.mail = mail

    def commit(self):
        pass

    def add(self, item):
        if isinstance(item, BusinessMailAttempt):
            item.attempted_at = datetime.now()
            self.mail.attempts.append(item)

    def query(self, model):
        assert model is BusinessMail
        return _MailQuery(self.mail)


def _pending_mail():
    return SimpleNamespace(
        id=uuid4(),
        source_kind="project_manual",
        project_type="translation",
        consultation_id=None,
        translation_project_id=uuid4(),
        interpretation_project_id=None,
        annotation_project_id=None,
        recruitment_project_id=None,
        subject="项目邮件",
        body="正文",
        status="pending",
        recipients=[SimpleNamespace(
            user_id=uuid4(), recipient_type="to", display_name_snapshot="收件人",
            email_snapshot="recipient@example.com",
        )],
        attempts=[],
        smtp_message_id="<project-mail-test@xinshi-system.local>",
        send_error=None,
        delivery_mode=None,
        created_at=datetime.now(),
        send_attempted_at=None,
        sent_at=None,
    )


def test_retry_attempt_uses_retrying_actor_and_preserves_each_sender(monkeypatch):
    mail = _pending_mail()
    db = _MailDb(mail)
    first_actor = _user("first@example.com", "首次发送人")
    retry_actor = _user("retry@example.com", "重试操作人")

    def sender_settings(_db, actor):
        settings = _settings()
        settings = SmtpSettings(**{
            **settings.__dict__,
            "username": actor.email,
            "password": "secret",
            "sender_email": actor.email,
            "sender_name": actor.full_name,
            "reply_to": actor.email,
        })
        return settings, {
            "sender_mode": "personal",
            "sender_name": actor.full_name,
            "sender_email": actor.email,
            "sender_verified": True,
        }

    monkeypatch.setattr(business_mail_service, "resolve_project_sender", sender_settings)
    outcomes = iter([MailDeliveryError("第一次失败"), None])
    send_calls = []

    def send_email(**kwargs):
        send_calls.append(kwargs)
        outcome = next(outcomes)
        if outcome:
            raise outcome
        return MailSendResult(
            delivery_recipient="safe@example.com",
            message_id=kwargs["message_id"],
            delivery_mode="test",
        )

    monkeypatch.setattr(business_mail_service, "send_text_email", send_email)

    _deliver(db, mail, first_actor)
    assert mail.status == "failed"
    _deliver(db, mail, retry_actor)
    serialized = serialize_mail(mail)

    assert mail.status == "sent"
    assert [item["sender_email"] for item in serialized["attempts"]] == [
        "first@example.com",
        "retry@example.com",
    ]
    assert [item["to_display_names"] for item in send_calls] == [
        {"recipient@example.com": "收件人"},
        {"recipient@example.com": "收件人"},
    ]
    assert serialized["sender_name"] == "重试操作人"
    assert serialized["sender_email"] == "retry@example.com"
