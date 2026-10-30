"""失败文件补提取只写独立批次，并支持断点重跑。"""

import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import collect_resume_text as collector  # noqa: E402
import recover_failed_resume_text as recovery  # noqa: E402


def test_retry_failed_is_isolated_and_incremental(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    readable = source / "rich.docx"
    readable.write_bytes(b"{\\rtf1\\ansi French resume}")
    broken = source / "broken.docx"
    broken.write_bytes(b"PKnot-a-valid-zip")
    collection = tmp_path / "collection"
    collection.mkdir()
    database = sqlite3.connect(collection / "state.sqlite3")
    collector.database(database)
    for path in (readable, broken):
        stat = path.stat()
        database.execute(
            "INSERT INTO files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(path), str(source), path.name, ".docx", stat.st_size, stat.st_mtime_ns,
             collector.file_time(stat.st_mtime), "", "failed", "BadZipFile", 0, 0,
             collector.now_iso(), collector.file_id(str(path))),
        )
    database.commit()
    database.close()

    output = tmp_path / "recovery"
    report = recovery.run([collection], output, 1, 10)
    assert report["counts"] == {"success": 1, "failed": 1}
    assert report["attempted"] == 1
    assert report["deferred"] == 1
    state = sqlite3.connect(collection / "state.sqlite3")
    assert state.execute("SELECT DISTINCT status FROM files").fetchall() == [("failed",)]
    state.close()
    recovered = sqlite3.connect(output / "state.sqlite3")
    first_time = recovered.execute("SELECT processed_at FROM files WHERE path=?", (str(readable),)).fetchone()[0]
    recovered.close()

    again = recovery.run([collection], output, 1, 10)
    assert again["attempted"] == 0
    recovered = sqlite3.connect(output / "state.sqlite3")
    assert recovered.execute("SELECT processed_at FROM files WHERE path=?", (str(readable),)).fetchone()[0] == first_time
    recovered.close()
