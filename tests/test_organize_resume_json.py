"""简历 JSON 归档分类回归。"""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collector = load("collect_resume_text")
organizer = load("organize_resume_json")


def test_first_foreign_precedes_second_and_folder(tmp_path):
    assert organizer.first_foreign_from_text("第一外语：\n第二外语：英语")[0] is None
    source = tmp_path / "来源"
    (source / "1. 英语").mkdir(parents=True)
    (source / "2. 日语").mkdir()
    (source / "杂项").mkdir()
    (source / "1. 英语" / "甲.txt").write_text("第一外语：法语\n第二外语：英语", encoding="utf-8")
    (source / "2. 日语" / "乙.txt").write_text("其他外语：英语", encoding="utf-8")
    (source / "杂项" / "丙.txt").write_text("第二外语：德语", encoding="utf-8")
    (source / "1. 英语" / "照片.jpg").write_bytes(b"image")
    collection = tmp_path / "collection"
    output = tmp_path / "organized"
    assert collector.collect([str(source)], collection, 2, 15) == 0

    report = organizer.organize([collection], output)
    assert report["total"] == 4
    assert report["by_language"] == {"法语": 1, "日语": 1, "待确认": 1, "英语": 1}
    records = {data["source_relative_path"]: data for path in output.glob("*/*.json") if (data := json.loads(path.read_text(encoding="utf-8")))}
    french = next(value for key, value in records.items() if key.endswith("甲.txt"))
    assert french["primary_language"] == "法语"
    assert french["classification_basis"] == "explicit_first_foreign"
    assert french["folder_conflict"] is True
    assert french["source_path"] == str(source / "1. 英语" / "甲.txt")
    assert french["raw_text"].startswith("第一外语")
    assert next(value for key, value in records.items() if key.endswith("乙.txt"))["primary_language"] == "日语"
    assert next(value for key, value in records.items() if key.endswith("丙.txt"))["primary_language"] == "待确认"
    assert next(value for key, value in records.items() if key.endswith("照片.jpg"))["raw_text"] is None

    before = {path: path.stat().st_mtime_ns for path in output.glob("*/*.json")}
    organizer.organize([collection], output)
    assert before == {path: path.stat().st_mtime_ns for path in output.glob("*/*.json")}
