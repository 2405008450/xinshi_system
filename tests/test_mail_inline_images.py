import io
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image

import mail_service
import mail_inline_image_service
from mail_inline_image_service import (
    MAX_INLINE_IMAGE_BYTES,
    load_owned_images,
    load_owned_or_bound_images,
    normalize_uploaded_image,
    prepare_trusted_mail_html,
    sanitize_body_html,
)
from mail_service import MailAttachment, MailConfigurationError, MailInlineImagePart, SmtpSettings, send_text_email


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


def _settings():
    return SmtpSettings(
        mode="test", host="smtp.example.com", port=25, security="none",
        username="", password="", sender_email="system@example.com",
        sender_name="信实系统", reply_to="", timeout_seconds=5,
        test_recipient="safe@example.com",
    )


def _image_bytes(fmt="JPEG", size=(2600, 1200)):
    output = io.BytesIO()
    Image.new("RGB", size, (30, 120, 210)).save(output, format=fmt, quality=90)
    return output.getvalue()


def test_normalize_uploaded_image_resizes_and_normalizes_format():
    content, content_type, width, height, extension = normalize_uploaded_image(
        _image_bytes(), "image/jpeg"
    )

    assert max(width, height) == 1920
    assert content_type == "image/jpeg"
    assert extension == ".jpg"
    assert len(content) <= MAX_INLINE_IMAGE_BYTES


def test_normalize_uploaded_image_rejects_mime_spoof_and_oversize():
    with pytest.raises(ValueError, match="格式与文件内容不匹配"):
        normalize_uploaded_image(_image_bytes(), "image/png")
    with pytest.raises(ValueError, match="2MB"):
        normalize_uploaded_image(b"x" * (MAX_INLINE_IMAGE_BYTES + 1), "image/jpeg")


def test_sanitize_body_html_only_keeps_bound_images_and_safe_tags():
    image_id = uuid4()
    image = SimpleNamespace(id=image_id)
    result = sanitize_body_html(
        f'<p onclick="bad()">正文<script>alert(1)</script></p>'
        f'<img src="https://evil.example/a.png" data-mail-image-id="{image_id}" alt="截图">',
        "正文",
        [image],
    )

    assert "onclick" not in result
    assert "script" not in result
    assert "https://evil.example" not in result
    assert f'data-mail-image-id="{image_id}"' in result


def test_sanitize_body_html_rejects_unbound_image():
    with pytest.raises(ValueError, match="未授权图片"):
        sanitize_body_html(
            f'<img data-mail-image-id="{uuid4()}" alt="越权图片">',
            "正文",
            [SimpleNamespace(id=uuid4())],
        )


class _ImageQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        return self

    def all(self):
        return self.rows


class _ImageDb:
    def __init__(self, rows):
        self.rows = rows

    def query(self, _model):
        return _ImageQuery(self.rows)


class _AuthorizedImageDb:
    def __init__(self, images, bindings):
        self.images = images
        self.bindings = bindings

    def query(self, model):
        from mail_inline_image_models import MailInlineImage, MailInlineImageBinding
        return _ImageQuery(self.images if model is MailInlineImage else self.bindings if model is MailInlineImageBinding else [])


def test_load_owned_images_rejects_other_users_and_total_limit():
    owner = uuid4()
    image_ids = [uuid4() for _ in range(5)]
    rows = [SimpleNamespace(id=image_id, uploaded_by=owner, file_size=2 * 1024 * 1024) for image_id in image_ids]
    with pytest.raises(ValueError, match="合计不能超过 8MB"):
        load_owned_images(_ImageDb(rows), image_ids, owner)

    rows[0].file_size = 1
    rows[0].uploaded_by = uuid4()
    with pytest.raises(PermissionError, match="其他用户"):
        load_owned_images(_ImageDb(rows), image_ids, owner)


def test_load_owned_images_rejects_more_than_five_images_without_querying():
    with pytest.raises(ValueError, match="最多插入 5 张"):
        load_owned_images(_ImageDb([]), [uuid4() for _ in range(6)], uuid4())


def test_bound_image_can_be_reused_by_another_authorized_sender():
    image_id = uuid4()
    scope_id = uuid4()
    image = SimpleNamespace(id=image_id, uploaded_by=uuid4(), file_size=1024)
    binding = SimpleNamespace(image_id=image_id, scope_type="manuscript_arrangement", scope_id=scope_id)

    result = load_owned_or_bound_images(
        _AuthorizedImageDb([image], [binding]),
        [image_id],
        uuid4(),
        scope_type="manuscript_arrangement",
        scope_id=scope_id,
    )

    assert result == [image]


def test_prepare_trusted_html_reads_file_and_replaces_cid(tmp_path, monkeypatch):
    image_id = uuid4()
    (tmp_path / "image.jpg").write_bytes(b"jpeg-content")
    monkeypatch.setattr(mail_inline_image_service, "get_mail_inline_image_dir", lambda: tmp_path)
    image = SimpleNamespace(
        id=image_id, storage_name="image.jpg", original_name="截图.jpg",
        content_type="image/jpeg",
    )

    rendered, parts = prepare_trusted_mail_html(
        f'<div><img data-mail-image-id="{image_id}" alt="截图"></div>',
        [image],
    )

    assert f"cid:mail-image-{image_id}@xinshi-system.local" in rendered
    assert "data-mail-image-id" not in rendered
    assert parts[0].content == b"jpeg-content"


def test_send_text_email_builds_related_cid_image(monkeypatch):
    monkeypatch.setattr(mail_service.smtplib, "SMTP", _FakeSmtp)
    send_text_email(
        to_emails=["employee@example.com"], subject="含图片邮件", body="纯文本正文",
        html_body='<p>HTML 正文</p><img src="cid:sample@xinshi-system.local">',
        inline_images=[MailInlineImagePart(
            cid="sample@xinshi-system.local", filename="截图.jpg",
            content=b"jpeg-content", content_type="image/jpeg",
        )],
        message_id="<inline-image-test@xinshi-system.local>", settings=_settings(),
    )

    message = _FakeSmtp.last_message
    assert message.get_content_type() == "multipart/mixed"
    mixed_parts = list(message.iter_parts())
    assert [part.get_content_type() for part in mixed_parts] == ["multipart/alternative"]
    alternative_parts = list(mixed_parts[0].iter_parts())
    assert [part.get_content_type() for part in alternative_parts] == [
        "text/plain",
        "multipart/related",
    ]
    related_parts = list(alternative_parts[1].iter_parts())
    assert [part.get_content_type() for part in related_parts] == ["text/html", "image/jpeg"]
    assert message.get_body(preferencelist=("plain",)).get_content_type() == "text/plain"
    assert message.get_body(preferencelist=("html",)).get_content_type() == "text/html"
    related = [part for part in message.walk() if part.get_content_type() == "image/jpeg"]
    assert len(related) == 1
    assert related[0]["Content-ID"] == "<sample@xinshi-system.local>"
    assert related[0].get_content_disposition() == "inline"


def test_send_text_email_keeps_plain_and_html_only_structures(monkeypatch):
    monkeypatch.setattr(mail_service.smtplib, "SMTP", _FakeSmtp)
    send_text_email(
        to_emails=["employee@example.com"], subject="纯文本邮件", body="纯文本正文",
        message_id="<plain-test@xinshi-system.local>", settings=_settings(),
    )
    assert _FakeSmtp.last_message.get_content_type() == "text/plain"

    send_text_email(
        to_emails=["employee@example.com"], subject="HTML 邮件", body="纯文本正文",
        html_body="<p>HTML 正文</p>",
        message_id="<html-test@xinshi-system.local>", settings=_settings(),
    )
    assert _FakeSmtp.last_message.get_content_type() == "multipart/alternative"
    assert [part.get_content_type() for part in _FakeSmtp.last_message.iter_parts()] == [
        "text/plain",
        "text/html",
    ]


def test_send_text_email_keeps_inline_images_related_with_regular_attachment(monkeypatch):
    monkeypatch.setattr(mail_service.smtplib, "SMTP", _FakeSmtp)
    send_text_email(
        to_emails=["employee@example.com"], subject="带附件的图片邮件", body="纯文本正文",
        html_body='<p>HTML 正文</p><img src="cid:sample@xinshi-system.local">',
        inline_images=[MailInlineImagePart(
            cid="sample@xinshi-system.local", filename="截图.jpg",
            content=b"jpeg-content", content_type="image/jpeg",
        )],
        attachments=[MailAttachment(
            filename="资料.pdf", content=b"pdf-content", content_type="application/pdf",
        )],
        message_id="<inline-attachment-test@xinshi-system.local>", settings=_settings(),
    )

    message = _FakeSmtp.last_message
    assert message.get_content_type() == "multipart/mixed"
    mixed_parts = list(message.iter_parts())
    assert [part.get_content_type() for part in mixed_parts] == [
        "multipart/alternative",
        "application/pdf",
    ]
    related_parts = list(list(mixed_parts[0].iter_parts())[1].iter_parts())
    assert [part.get_content_type() for part in related_parts] == ["text/html", "image/jpeg"]
    assert related_parts[1].get_content_disposition() == "inline"
    assert mixed_parts[1].get_content_disposition() == "attachment"


def test_send_text_email_rejects_inline_image_without_html_body(monkeypatch):
    monkeypatch.setattr(mail_service.smtplib, "SMTP", _FakeSmtp)
    with pytest.raises(MailConfigurationError, match="HTML 正文"):
        send_text_email(
            to_emails=["employee@example.com"], subject="缺少 HTML 正文", body="纯文本正文",
            inline_images=[MailInlineImagePart(
                cid="sample@xinshi-system.local", filename="截图.jpg",
                content=b"jpeg-content", content_type="image/jpeg",
            )],
            message_id="<missing-html-test@xinshi-system.local>", settings=_settings(),
        )
