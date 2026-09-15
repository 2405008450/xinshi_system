from pathlib import Path

import pytest

from project_file_service import build_source_file_name, collect_source_file_names


def test_collect_source_file_names_reads_first_level_and_ignores_temporary_files(tmp_path: Path):
    (tmp_path / "B文件.pdf").write_bytes(b"pdf")
    (tmp_path / "a文件.docx").write_bytes(b"docx")
    (tmp_path / "~$a文件.docx").write_bytes(b"temporary")
    (tmp_path / "desktop.ini").write_bytes(b"system")
    nested = tmp_path / "子目录"
    nested.mkdir()
    (nested / "不递归读取.txt").write_bytes(b"nested")

    assert collect_source_file_names(tmp_path) == ["a文件.docx", "B文件.pdf"]


def test_collect_source_file_names_accepts_a_file_path(tmp_path: Path):
    source = tmp_path / "单个原文.docx"
    source.write_bytes(b"content")

    assert collect_source_file_names(source) == ["单个原文.docx"]


def test_collect_source_file_names_rejects_empty_directory(tmp_path: Path):
    with pytest.raises(ValueError, match="没有可读取的文件"):
        collect_source_file_names(tmp_path)


def test_build_source_file_name_joins_multiple_files():
    assert build_source_file_name(["A.docx", "B.xlsx"]) == "A.docx；B.xlsx"


def test_build_source_file_name_summarizes_when_field_limit_is_exceeded():
    result = build_source_file_name(["A" * 250 + ".docx", "B.xlsx"])

    assert len(result) <= 255
    assert result.endswith("等 2 个文件")
