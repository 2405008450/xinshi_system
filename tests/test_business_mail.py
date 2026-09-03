from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

import mail_service
import business_mail_service
from business_mail_service import _require_subject_order_no, build_preview
from business_mail_schemas import BusinessMailSendRequest, MailRecipientGroupWrite
from interpretation_models import InterpretationLanguage
from mail_service import MailAttachment, SmtpSettings, send_text_email
from utils import normalize_email_subject_order_no


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


def test_send_text_email_adds_uploaded_attachment(monkeypatch):
    monkeypatch.setattr(mail_service.smtplib, "SMTP", _FakeSmtp)

    send_text_email(
        to_emails=["employee1@example.com"],
        subject="稿件安排",
        body="请查收附件",
        attachments=[MailAttachment(
            filename="测试稿件.docx",
            content=b"document-content",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )],
        message_id="<attachment-test@xinshi-system.local>",
        settings=_settings(),
    )

    attachments = list(_FakeSmtp.last_message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "测试稿件.docx"
    assert attachments[0].get_payload(decode=True) == b"document-content"


def test_live_mode_keeps_sender_self_copy(monkeypatch):
    monkeypatch.setattr(mail_service.smtplib, "SMTP", _FakeSmtp)

    send_text_email(
        to_emails=["translator@example.com"],
        cc_emails=["system@example.com"],
        subject="稿件安排",
        body="请查收附件",
        message_id="<self-copy-test@xinshi-system.local>",
        settings=_settings(mode="live"),
    )

    assert _FakeSmtp.last_message["To"] == "translator@example.com"
    assert _FakeSmtp.last_message["Cc"] == "system@example.com"


def test_live_mode_adds_internal_recipient_display_names(monkeypatch):
    monkeypatch.setattr(mail_service.smtplib, "SMTP", _FakeSmtp)

    result = send_text_email(
        to_emails=["hr7@xinshifanyi.com.cn"],
        cc_emails=["service3@xinshifanyi.com.cn"],
        to_display_names={"HR7@XINSHIFANYI.COM.CN": "信实翻译-HR专员彭舒婷"},
        cc_display_names={"service3@xinshifanyi.com.cn": "信实翻译-客户专员刘家铭"},
        subject="新项目",
        body="项目内容",
        message_id="<named-recipient-test@xinshi-system.local>",
        settings=_settings(mode="live"),
    )

    assert str(_FakeSmtp.last_message["To"]) == "信实翻译-HR专员彭舒婷 <hr7@xinshifanyi.com.cn>"
    assert str(_FakeSmtp.last_message["Cc"]) == "信实翻译-客户专员刘家铭 <service3@xinshifanyi.com.cn>"
    assert result.delivery_recipient == (
        "hr7@xinshifanyi.com.cn, service3@xinshifanyi.com.cn"
    )


def test_recipient_display_name_rejects_header_injection(monkeypatch):
    monkeypatch.setattr(mail_service.smtplib, "SMTP", _FakeSmtp)

    with pytest.raises(mail_service.MailConfigurationError, match="显示名称不能包含换行"):
        send_text_email(
            to_emails=["employee@example.com"],
            to_display_names={"employee@example.com": "正常姓名\nBcc: outsider@example.com"},
            subject="新项目",
            body="项目内容",
            message_id="<display-name-injection-test@xinshi-system.local>",
            settings=_settings(mode="live"),
        )


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


def test_new_project_subject_replaces_preview_order_with_final_order():
    subject = "***急***，TP-260902-005，梁伟，英译中，9月2日16点回稿"

    normalized = normalize_email_subject_order_no(subject, "TP-260902-007")

    assert normalized == "***急***，TP-260902-007，梁伟，英译中，9月2日16点回稿"


def test_business_mail_subject_must_include_authoritative_order_no():
    project = SimpleNamespace(order_no="TP-260902-007")

    _require_subject_order_no(project, "***急***，TP-260902-007，梁伟")
    with pytest.raises(ValueError, match="TP-260902-007"):
        _require_subject_order_no(project, "***急***，TP-260902-005，梁伟")


def test_translation_preview_allows_missing_customer_deadline(monkeypatch):
    monkeypatch.setattr(business_mail_service, "policy_recipients", lambda *_args: ([], []))
    monkeypatch.setattr(business_mail_service.SmtpSettings, "from_env", lambda: _settings())

    preview = build_preview(object(), "translation", source={
        "order_no": "TP-260831-001",
        "project_name": "待确认交稿时间项目",
        "service_content": "翻译",
        "language_pair": "中英",
    })

    assert "客户交稿时间" not in preview["missing_fields"]
    assert not any("客户交稿时间" in reason for reason in preview["blocking_reasons"])


def test_translation_preview_shows_missing_core_fields_in_body(monkeypatch):
    monkeypatch.setattr(business_mail_service, "policy_recipients", lambda *_args: ([], []))
    monkeypatch.setattr(business_mail_service.SmtpSettings, "from_env", lambda: _settings())

    preview = build_preview(object(), "translation", source={
        "order_no": "TP-260831-003",
        "project_name": "待补核心字段项目",
    })

    assert preview["missing_fields"] == ["服务内容", "翻译方向"]
    assert "服务内容：（待填写）" in preview["body"]
    assert "翻译方向：（待填写）" in preview["body"]
    assert "文本类型：（待填写）" not in preview["body"]


def test_translation_preview_uses_customer_deadline_business_label(monkeypatch):
    monkeypatch.setattr(business_mail_service, "policy_recipients", lambda *_args: ([], []))
    monkeypatch.setattr(business_mail_service.SmtpSettings, "from_env", lambda: _settings())

    preview = build_preview(object(), "translation", source={
        "order_no": "TP-260831-002",
        "project_name": "已确认交稿时间项目",
        "service_content": "翻译",
        "language_pair": "中英",
        "customer_deadline_time": "2026-09-01 18:00",
    })

    assert "客户交稿时间：2026-09-01 18:00" in preview["body"]
    assert "客户交期：" not in preview["body"]


def test_translation_preview_contains_complete_project_word_count_matrix(monkeypatch):
    monkeypatch.setattr(business_mail_service, "policy_recipients", lambda *_args: ([], []))
    monkeypatch.setattr(business_mail_service.SmtpSettings, "from_env", lambda: _settings())

    preview = build_preview(object(), "translation", source={
        "order_no": "TP-260901-001",
        "project_name": "字数统计项目",
        "service_content": "翻译",
        "language_pair": "中英",
        "word_count_matrix": {
            "company": {"words": 1200, "pages": 5},
            "customer": {"characters_no_spaces": 2345},
            "translator_estimate": {"foreign_words": 1000, "documents": 2},
            "translators": [{
                "translator_name": "张译员",
                "planned": {"words": 900},
                "actual": {"words": 950, "pages": 4},
            }],
        },
    })

    assert "项目字数统计：" in preview["body"]
    assert "我司字数：字数 1,200；页数 5" in preview["body"]
    assert "客户字数：字符数（不计空格） 2,345" in preview["body"]
    assert "译员预定（项目预估）：外文字数 1,000；份数 2" in preview["body"]
    assert "张译员 · 预定：字数 900" in preview["body"]
    assert "张译员 · 实际：字数 950；页数 4" in preview["body"]


def test_recipient_group_requires_name_and_internal_members():
    with pytest.raises(ValidationError):
        MailRecipientGroupWrite(name="   ", user_ids=[])


class _LanguageQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        return self

    def all(self):
        return self.rows


class _InterpretationPreviewDb:
    def __init__(self, languages):
        self.languages = languages

    def query(self, target):
        assert target is InterpretationLanguage
        return _LanguageQuery(self.languages)


def test_interpretation_preview_uses_business_labels_instead_of_internal_values(monkeypatch):
    source_language_id = uuid4()
    target_language_id = uuid4()
    extra_language_id = uuid4()
    db = _InterpretationPreviewDb([
        SimpleNamespace(id=source_language_id, label="英语"),
        SimpleNamespace(id=target_language_id, label="中文（简体）"),
        SimpleNamespace(id=extra_language_id, label="日语"),
    ])
    monkeypatch.setattr(business_mail_service, "policy_recipients", lambda *_args: ([], []))
    monkeypatch.setattr(business_mail_service.SmtpSettings, "from_env", lambda: _settings())

    preview = build_preview(db, "interpretation", source={
        "order_no": "IP-260827-001",
        "project_name": "Jimmy-260827",
        "client_short_name": "Jimmy",
        "manager_contact": "10086",
        "project_types": ["onsite"],
        "time_ranges": [{
            "scheduled_start": datetime(2026, 8, 28, 0, 0),
            "scheduled_end": datetime(2026, 8, 30, 0, 0),
            "actual_start": None,
            "actual_end": None,
        }],
        "locations": ["阿拉斯加"],
        "language_directions": [{
            "language_ids": [source_language_id, target_language_id, extra_language_id],
            "required_count": 1,
        }],
        "required_interpreter_count": 1,
        "consultation_description": "英语展会陪同",
    })

    assert "项目类型：口译" in preview["body"]
    assert "口译类型：现场口译" in preview["body"]
    assert "预定时段：2026-08-28 00:00 至 2026-08-30 00:00" in preview["body"]
    assert "口译方向：英语 ↔ 中文（简体） ↔ 日语" in preview["body"]
    assert "英语 ↔ 中文（简体） ↔ 日语（1人）" in preview["body"]
    assert "总需求人数：1" in preview["body"]
    assert preview["body"].count("项目类型：") == 1
    assert "onsite" not in preview["body"]
    assert "datetime.datetime" not in preview["body"]
    assert str(source_language_id) not in preview["body"]


def test_annotation_preview_uses_chinese_types_and_readable_languages(monkeypatch):
    source_language_id = uuid4()
    db = _InterpretationPreviewDb([
        SimpleNamespace(id=source_language_id, label="泉州闽南语"),
    ])
    monkeypatch.setattr(business_mail_service, "policy_recipients", lambda *_args: ([], []))
    monkeypatch.setattr(business_mail_service.SmtpSettings, "from_env", lambda: _settings())

    preview = build_preview(db, "annotation", source={
        "order_no": "AP-260828-001",
        "project_name": "GRAY-标注",
        "project_types": ["audio_collection", "text_annotation"],
        "task_description": "听音转写",
        "language_items": [{"source_language_id": source_language_id}],
    })

    assert "项目类型：音频采集；文本标注" in preview["body"]
    assert "语言范围：泉州闽南语" in preview["body"]
    assert "audio_collection" not in preview["body"]
    assert "source_language_id" not in preview["body"]
    assert str(source_language_id) not in preview["body"]
