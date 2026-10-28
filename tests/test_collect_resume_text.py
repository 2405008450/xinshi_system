"""简历原文采集的本地隔离回归。"""

import importlib.util
import json
import os
import subprocess
import zipfile
from pathlib import Path

from openpyxl import Workbook


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "collect_resume_text.py"
spec = importlib.util.spec_from_file_location("collect_resume_text", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_collect_and_resume(tmp_path):
    source = tmp_path / "来源"
    output = tmp_path / "结果"
    source.mkdir()
    (source / "中文简历.txt").write_text("姓名：测试人员\n经验：标注", encoding="utf-8")
    (source / "照片.jpg").write_bytes(b"fake image")
    (source / "~$临时.docx").write_bytes(b"not a resume")
    with zipfile.ZipFile(source / "资料.docx", "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>第一段</w:t></w:r></w:p><w:p><w:r><w:t>第二段</w:t></w:r></w:p></w:body></w:document>',
        )
    book = Workbook()
    book.active["B2"] = "只在第二列"
    book.save(source / "稀疏表格.xlsx")

    assert module.collect([str(source)], output, 2, 15) == 0
    manifest = [json.loads(line) for line in (output / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(manifest) == 5
    assert {row["status"] for row in manifest} == {"success", "skipped"}
    text_row = next(row for row in manifest if row["path"].endswith("中文简历.txt"))
    doc_row = next(row for row in manifest if row["path"].endswith("资料.docx"))
    assert text_row["path"] == str(source / "中文简历.txt")
    assert "测试人员" in (output / text_row["text_file"]).read_text(encoding="utf-8")
    assert "第一段" in (output / doc_row["text_file"]).read_text(encoding="utf-8")
    assert len(json.loads((output / doc_row["segments_file"]).read_text(encoding="utf-8"))) == 2
    sheet_row = next(row for row in manifest if row["path"].endswith("稀疏表格.xlsx"))
    assert "第 2 行" in (output / sheet_row["segments_file"]).read_text(encoding="utf-8")
    lock_row = next(row for row in manifest if row["path"].endswith("~$临时.docx"))
    assert (lock_row["status"], lock_row["reason"]) == ("skipped", "office_lock_file")

    previous = text_row["processed_at"]
    assert module.collect([str(source)], output, 2, 15) == 0
    again = [json.loads(line) for line in (output / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    assert next(row for row in again if row["path"].endswith("中文简历.txt"))["processed_at"] == previous

    (source / "中文简历.txt").write_text("姓名：另一人员\n经验：口译", encoding="utf-8")
    assert module.collect([str(source)], output, 2, 15) == 0
    changed = [json.loads(line) for line in (output / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    changed_row = next(row for row in changed if row["path"].endswith("中文简历.txt"))
    assert "另一人员" in (output / changed_row["text_file"]).read_text(encoding="utf-8")
    assert changed_row["sha256"] != text_row["sha256"]


def test_failed_file_retries_and_unavailable_root(tmp_path):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    target = source / "broken.docx"
    target.write_bytes(b"broken")
    assert module.collect([str(source)], output, 1, 10) == 1
    first = json.loads((output / "manifest.jsonl").read_text(encoding="utf-8"))
    assert first["status"] == "failed"
    assert module.collect([str(source)], output, 1, 10) == 1
    second = json.loads((output / "manifest.jsonl").read_text(encoding="utf-8"))
    assert second["status"] == "failed"
    assert module.collect([str(source / "missing")], tmp_path / "other-output", 1, 10) == 1
    report = json.loads((tmp_path / "other-output" / "report.json").read_text(encoding="utf-8"))
    assert report["scan_errors"][0]["reason"] == "root_unavailable"


def test_worker_timeout_terminates_process_tree(tmp_path, monkeypatch):
    source = tmp_path / "stuck.doc"
    source.write_bytes(b"data")
    output = tmp_path / "output"
    for name in ("tmp", "texts", "segments"):
        (output / name).mkdir(parents=True)

    class StuckProcess:
        pid = 1234

        def wait(self, timeout):
            raise subprocess.TimeoutExpired("worker", timeout)

    terminated = []
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: StuckProcess())
    monkeypatch.setattr(module, "terminate_process_tree", lambda process: terminated.append(process.pid))

    result = module.process_one(str(source), str(tmp_path), source.name, source.stat(), output, 5)
    assert terminated == [1234]
    assert (result["status"], result["reason"]) == ("failed", "timeout")


def test_stale_doc_temp_cleanup_preserves_recent_directory(tmp_path, monkeypatch):
    temp_root = tmp_path / "doc-temp"
    temp_root.mkdir()
    stale = temp_root / "resume-doc-abcdefgh"
    recent = temp_root / "resume-doc-ijklmnop"
    stale.mkdir()
    recent.mkdir()
    (stale / "lu.tmp").write_bytes(b"temporary")
    os.utime(stale, (1000, 1000))
    monkeypatch.setenv("RESUME_TEMP_DIR", str(temp_root))

    module.cleanup_stale_doc_temps()

    assert not stale.exists()
    assert recent.exists()
