"""把试点选中的采集文本打包供有官方模型密钥的开发机处理。"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import zipfile
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path


TZ = timezone(timedelta(hours=8))


def package(selection: Path, staging: Path, archive: Path) -> dict:
    if not selection.is_file():
        raise FileNotFoundError(selection)
    if staging.resolve() in archive.resolve().parents:
        raise ValueError("archive_must_be_outside_staging")
    if staging.exists() or archive.exists():
        raise FileExistsError("staging_or_archive_exists")
    staging.mkdir(parents=True)
    with closing(sqlite3.connect(f"file:{selection.as_posix()}?mode=ro", uri=True)) as selected:
        rows = selected.execute("SELECT file_id,collection FROM selected ORDER BY rank").fetchall()
    grouped: dict[Path, list[str]] = {}
    for file_id, collection in rows:
        if len(file_id) != 64 or any(c not in "0123456789abcdef" for c in file_id):
            raise ValueError("file_id_invalid")
        grouped.setdefault(Path(collection), []).append(file_id)
    copied = 0
    missing = 0
    for collection, file_ids in grouped.items():
        target = staging / collection.name
        target.mkdir(exist_ok=True)
        for folder in ("texts", "segments"):
            (target / folder).mkdir(exist_ok=True)
        (target / "origin.json").write_text(json.dumps({"collection": str(collection)}, ensure_ascii=False), encoding="utf-8")
        with closing(sqlite3.connect(f"file:{(collection / 'state.sqlite3').as_posix()}?mode=ro", uri=True)) as source:
            source.row_factory = sqlite3.Row
            create_sql = source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='files'").fetchone()[0]
            wanted = set(file_ids)
            source_rows = {row["file_id"]: row for row in source.execute("SELECT * FROM files WHERE status='success'")
                           if row["file_id"] in wanted}
            with closing(sqlite3.connect(target / "state.sqlite3")) as snapshot:
                snapshot.execute(create_sql)
                for file_id in file_ids:
                    row = source_rows.get(file_id)
                    if row is None:
                        missing += 1
                        continue
                    original = [collection / folder / f"{file_id}.{suffix}" for folder, suffix in (("texts", "txt"), ("segments", "json"))]
                    if not all(path.is_file() for path in original):
                        missing += 1
                        continue
                    before = [(path.stat().st_size, path.stat().st_mtime_ns) for path in original]
                    for path in original:
                        shutil.copy2(path, target / path.parent.name / path.name)
                    after = [(path.stat().st_size, path.stat().st_mtime_ns) for path in original]
                    if before != after:
                        missing += 1
                        continue
                    current = source.execute("SELECT sha256,processed_at,status FROM files WHERE path=?", (row["path"],)).fetchone()
                    if current is None or tuple(current) != (row["sha256"], row["processed_at"], row["status"]):
                        missing += 1
                        continue
                    snapshot.execute("INSERT INTO files VALUES (" + ",".join("?" for _ in row) + ")", tuple(row))
                    copied += 1
                snapshot.commit()
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as bundle:
        for path in staging.rglob("*"):
            if path.is_file():
                bundle.write(path, path.relative_to(staging.parent))
    return {"created_at": datetime.now(TZ).isoformat(timespec="seconds"),
            "selected": len(rows), "copied": copied, "deferred": missing,
            "archive": str(archive)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.selection, args.staging, args.archive), ensure_ascii=False))


if __name__ == "__main__":
    main()
