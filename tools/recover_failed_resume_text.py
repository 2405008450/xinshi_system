"""把既有失败简历补提取到独立批次，不改动原采集状态和语种归档。"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from pathlib import Path

import collect_resume_text as collector


COLUMNS = (
    "path", "root", "relative_path", "extension", "size", "mtime_ns", "modified_at",
    "sha256", "status", "reason", "characters", "segments", "processed_at", "file_id",
)


def failed_rows(collections: list[Path]):
    seen = set()
    roots = []
    rows = []
    for collection in collections:
        db = collection / "state.sqlite3"
        with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as source:
            for values in source.execute(
                f"SELECT {','.join(COLUMNS)} FROM files WHERE status='failed' ORDER BY path"
            ):
                row = dict(zip(COLUMNS, values))
                key = os.path.normcase(os.path.abspath(row["path"]))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
                if row["root"] not in roots:
                    roots.append(row["root"])
    return rows, roots


def run(collections: list[Path], output: Path, workers: int, timeout: int) -> dict:
    sources = [path.resolve() for path in collections]
    resolved_output = output.resolve()
    if any(resolved_output == source or source in resolved_output.parents for source in sources):
        raise ValueError("补提取目录不能位于原采集目录内")
    rows, roots = failed_rows(collections)
    collector.ensure_output_safe(output, roots)
    output.mkdir(parents=True, exist_ok=True)
    for name in ("texts", "segments", "tmp"):
        (output / name).mkdir(exist_ok=True)
    state = sqlite3.connect(output / "state.sqlite3")
    collector.database(state)
    collector.cleanup_stale_doc_temps()
    paths = set()
    attempted = 0
    deferred = 0
    completed = 0
    queued = {}

    def save(item: dict) -> None:
        state.execute(
            """INSERT INTO files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET root=excluded.root,relative_path=excluded.relative_path,
            extension=excluded.extension,size=excluded.size,mtime_ns=excluded.mtime_ns,
            modified_at=excluded.modified_at,sha256=excluded.sha256,status=excluded.status,
            reason=excluded.reason,characters=excluded.characters,segments=excluded.segments,
            processed_at=excluded.processed_at,file_id=excluded.file_id""",
            tuple(item[column] for column in COLUMNS),
        )
        state.commit()

    def save_done(future) -> None:
        nonlocal completed
        row, stat = queued.pop(future)
        try:
            item = future.result()
        except Exception as exc:
            item = {
                **row, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                "modified_at": collector.file_time(stat.st_mtime), "sha256": "",
                "status": "failed", "reason": type(exc).__name__, "characters": 0,
                "segments": 0, "processed_at": collector.now_iso(),
            }
        save(item)
        completed += 1
        if completed % 25 == 0:
            collector.cleanup_stale_doc_temps()
        if completed % 100 == 0:
            print(f"补提取已完成 {completed} 个尝试", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for row in rows:
            path = row["path"]
            paths.add(path)
            try:
                stat = os.stat(path)
            except OSError:
                save({**row, "sha256": "", "status": "failed", "reason": "source_unavailable",
                      "characters": 0, "segments": 0, "processed_at": collector.now_iso()})
                deferred += 1
                continue
            old = state.execute("SELECT size,mtime_ns,status,file_id FROM files WHERE path=?", (path,)).fetchone()
            if old and old[:2] == (stat.st_size, stat.st_mtime_ns) and old[2] == "success" and (output / "texts" / f"{old[3]}.txt").exists():
                continue
            try:
                with open(path, "rb") as source:
                    signature = source.read(8)
            except OSError:
                signature = b""
            if row["reason"] in {"DocTempLimitExceeded", "TimeoutExpired", "timeout"} or (
                row["reason"] == "BadZipFile" and signature.startswith(b"PK")
            ):
                save({
                    **row, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                    "modified_at": collector.file_time(stat.st_mtime),
                    "status": "failed", "reason": f"deferred_{row['reason']}",
                    "processed_at": collector.now_iso(),
                })
                deferred += 1
                continue
            future = executor.submit(
                collector.process_one, path, row["root"], row["relative_path"], stat, output, timeout
            )
            queued[future] = (row, stat)
            attempted += 1
            if len(queued) >= workers * 4:
                done, _ = wait(queued, return_when=FIRST_COMPLETED)
                for completed_future in done:
                    save_done(completed_future)
        for completed_future in as_completed(queued):
            save_done(completed_future)
    report = collector.export(state, output, roots, [], paths)
    report["attempted"] = attempted
    report["deferred"] = deferred
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    state.close()
    print(json.dumps({"total": report["total"], "counts": report["counts"],
                      "attempted": attempted, "deferred": deferred}, ensure_ascii=False), flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4 or args.timeout < 5:
        parser.error("--workers 须为 1-4，--timeout 不小于 5 秒")
    report = run(args.collection, args.output, args.workers, args.timeout)
    return 1 if report["counts"].get("failed", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
