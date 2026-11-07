from pathlib import Path

import pytest

from project_file_service import build_source_file_name, collect_source_file_names
import project_file_service as service


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


def test_build_source_file_name_rejects_multiple_files():
    with pytest.raises(ValueError, match="一个订单号只能对应一个文件名"):
        build_source_file_name(["A.docx", "B.xlsx"])


def test_build_source_file_name_never_truncates_extension():
    with pytest.raises(ValueError, match="不能超过"):
        build_source_file_name(["A" * 251 + ".docx"])
    assert build_source_file_name(["原文.docx"]) == "原文.docx"


def test_list_directory_preserves_invalid_rows(monkeypatch, tmp_path):
    monkeypatch.setenv('OPENPATH_ALLOWED_ROOTS', r'\\server\share')
    (tmp_path / '中文 空格.docx').touch()
    (tmp_path / '无扩展名').touch()
    (tmp_path / '危险.exe').touch()
    monkeypatch.setattr(service, 'Path', lambda _: tmp_path)
    result = service.list_sub_order_source_files(r'\\server\share\原文')
    rows = {row['name']: row for row in result['files']}
    assert rows['中文 空格.docx']['selectable']
    assert rows['中文 空格.docx']['path'] == r'\\server\share\原文\中文 空格.docx'
    assert not rows['无扩展名']['selectable']
    assert not rows['危险.exe']['selectable']


def test_directory_limit_and_reparse_points(monkeypatch, tmp_path):
    (tmp_path / 'A.docx').touch()
    (tmp_path / 'B.docx').touch()
    with pytest.raises(ValueError, match='超过'):
        collect_source_file_names(tmp_path, limit=1)
    monkeypatch.setattr(service, '_is_reparse_point', lambda path: path.name == 'A.docx')
    assert collect_source_file_names(tmp_path) == ['B.docx']


def test_picker_accepts_file(monkeypatch, tmp_path):
    monkeypatch.setenv('OPENPATH_ALLOWED_ROOTS', r'\\server\share')
    file = tmp_path / 'A.docx'
    file.touch()
    monkeypatch.setattr(service, 'Path', lambda _: file)
    result = service.list_sub_order_source_files(r'\\server\share\A.docx')
    assert result['files'] == [{'name': 'A.docx', 'path': r'\\server\share\A.docx', 'selectable': True, 'reason': ''}]


def test_directory_permission_error(monkeypatch):
    monkeypatch.setenv('OPENPATH_ALLOWED_ROOTS', r'\\server\share')
    monkeypatch.setattr(service, '_is_reparse_point', lambda _: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(ValueError, match='读取权限'):
        service.list_sub_order_source_files(r'\\server\share')
