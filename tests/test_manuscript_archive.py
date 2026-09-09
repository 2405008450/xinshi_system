import zipfile
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

import pytest

import mail_service
import manuscript_archive
from mail_service import MailAttachment
from manuscript_archive import (
    build_manuscript_path_archive,
    list_manuscript_directory,
    resolve_selected_dispatch_file,
    validate_manuscript_mail_size,
)
from manuscript_service import _validate_selected_file_snapshots


def test_build_archive_combines_dispatch_and_reference_directories(tmp_path):
    dispatch = tmp_path / "dispatch"
    reference = tmp_path / "reference"
    (dispatch / "nested").mkdir(parents=True)
    reference.mkdir()
    (dispatch / "稿件.docx").write_bytes(b"dispatch")
    (dispatch / "nested" / "说明.txt").write_text("说明", encoding="utf-8")
    (reference / "术语.xlsx").write_bytes(b"reference")

    attachment = build_manuscript_path_archive(
        str(dispatch),
        str(reference),
        filename_stem="XS-001",
    )

    assert attachment.filename == "XS-001-稿件资料.zip"
    assert attachment.content_type == "application/zip"
    with zipfile.ZipFile(BytesIO(attachment.content)) as archive:
        assert set(archive.namelist()) == {
            "派稿文/稿件.docx",
            "派稿文/nested/说明.txt",
            "参考文件/术语.xlsx",
        }
        assert archive.read("派稿文/稿件.docx") == b"dispatch"


def test_build_archive_deduplicates_same_shared_path(tmp_path):
    (tmp_path / "稿件.txt").write_text("content", encoding="utf-8")

    attachment = build_manuscript_path_archive(str(tmp_path), str(tmp_path))

    with zipfile.ZipFile(BytesIO(attachment.content)) as archive:
        assert archive.namelist() == ["派稿文/稿件.txt"]


def test_selected_archive_only_contains_selected_dispatch_files_and_all_references(tmp_path):
    dispatch = tmp_path / "dispatch"
    reference = tmp_path / "reference"
    (dispatch / "nested").mkdir(parents=True)
    reference.mkdir()
    (dispatch / "不发送.docx").write_bytes(b"skip")
    (dispatch / "nested" / "发送.txt").write_bytes(b"send")
    (reference / "术语.xlsx").write_bytes(b"reference")

    attachment = build_manuscript_path_archive(
        str(dispatch),
        str(reference),
        selected_dispatch_files=["nested/发送.txt"],
    )

    with zipfile.ZipFile(BytesIO(attachment.content)) as archive:
        assert set(archive.namelist()) == {
            "派稿文/nested/发送.txt",
            "参考文件/术语.xlsx",
        }


def test_dispatch_file_listing_is_lazy_and_rejects_traversal(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "稿件.docx").write_bytes(b"content")
    (tmp_path / "payload.exe").write_bytes(b"unsafe")
    (nested / "子文件.txt").write_bytes(b"nested")

    root_result = list_manuscript_directory(str(tmp_path))
    by_name = {item["name"]: item for item in root_result["items"]}
    assert by_name["nested"]["is_directory"] is True
    assert by_name["稿件.docx"]["selectable"] is True
    assert by_name["payload.exe"]["selectable"] is False
    assert all(item["name"] != "子文件.txt" for item in root_result["items"])

    nested_result = list_manuscript_directory(str(tmp_path), "nested")
    assert [item["relative_path"] for item in nested_result["items"]] == ["nested/子文件.txt"]
    with pytest.raises(ValueError, match="目录路径无效"):
        list_manuscript_directory(str(tmp_path), "../outside")
    with pytest.raises(ValueError, match="路径无效"):
        resolve_selected_dispatch_file(tmp_path, "../outside.txt")


def test_selected_file_snapshot_detects_change_before_send(tmp_path):
    file_path = tmp_path / "稿件.docx"
    file_path.write_bytes(b"original")
    stat = file_path.stat()
    arrangement = SimpleNamespace(
        file_selection_mode="selected",
        translator_name_snapshot="张三",
        selected_files=[SimpleNamespace(
            relative_path="稿件.docx",
            file_size=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime),
        )],
    )
    _validate_selected_file_snapshots(arrangement, str(tmp_path))

    file_path.write_bytes(b"changed content")
    with pytest.raises(ValueError, match="已发生变化"):
        _validate_selected_file_snapshots(arrangement, str(tmp_path))


def test_build_archive_rejects_empty_directories(tmp_path):
    with pytest.raises(ValueError, match="没有可发送的文件"):
        build_manuscript_path_archive(str(tmp_path), None)


def test_build_archive_rejects_dangerous_files(tmp_path):
    (tmp_path / "payload.exe").write_bytes(b"unsafe")

    with pytest.raises(ValueError, match="禁止发送的文件类型"):
        build_manuscript_path_archive(str(tmp_path), None)


def test_build_archive_uses_50mb_memory_attachment_limit(tmp_path, monkeypatch):
    assert manuscript_archive.MAX_MANUSCRIPT_ARCHIVE_BYTES == 50 * 1024 * 1024

    (tmp_path / "稿件.txt").write_bytes(b"content")
    monkeypatch.setattr(manuscript_archive, "MAX_MANUSCRIPT_ARCHIVE_BYTES", 1)

    with pytest.raises(ValueError, match="共享文件压缩包不能超过 50MB"):
        build_manuscript_path_archive(str(tmp_path), None)


def test_validate_mail_size_includes_manual_and_automatic_attachments(monkeypatch):
    monkeypatch.setattr(manuscript_archive, "MAX_MANUSCRIPT_MAIL_CONTENT_BYTES", 5)
    attachments = [
        MailAttachment(filename="manual.txt", content=b"123"),
        MailAttachment(filename="auto.zip", content=b"456"),
    ]

    with pytest.raises(ValueError, match="合计不能超过"):
        validate_manuscript_mail_size(attachments)


def test_plain_text_mail_keeps_manual_and_automatic_attachments(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        mail_service,
        "send_text_email",
        lambda **values: captured.update(values) or "sent",
    )
    manual = MailAttachment(filename="manual.txt", content=b"manual")
    automatic = MailAttachment(filename="archive.zip", content=b"archive")

    result = mail_service.send_plain_text_email(
        recipient_email="translator@example.com",
        cc_emails=["sender@example.com"],
        subject="subject",
        body="body",
        attachment=manual,
        attachments=[automatic],
        message_id="<test@example.com>",
    )

    assert result == "sent"
    assert captured["attachments"] == [manual, automatic]
    assert captured["cc_emails"] == ["sender@example.com"]
