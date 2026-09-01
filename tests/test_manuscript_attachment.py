import pytest
from fastapi import HTTPException

from routers.manuscript_arrangements import (
    MAX_MANUSCRIPT_ATTACHMENT_BYTES,
    validate_manuscript_attachment,
)


def test_manuscript_attachment_accepts_exactly_50mb_and_normalizes_name():
    attachment = validate_manuscript_attachment(
        r"C:\fakepath\稿件.docx",
        "application/octet-stream",
        b"x" * MAX_MANUSCRIPT_ATTACHMENT_BYTES,
    )

    assert attachment.filename == "稿件.docx"
    assert len(attachment.content) == MAX_MANUSCRIPT_ATTACHMENT_BYTES


def test_manuscript_attachment_rejects_file_over_50mb():
    with pytest.raises(HTTPException) as exc_info:
        validate_manuscript_attachment(
            "稿件.docx",
            "application/octet-stream",
            b"x" * (MAX_MANUSCRIPT_ATTACHMENT_BYTES + 1),
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "上传文件不能超过 50MB"
