"""撤回 10.26 表尾部误导入的 13 条未来日期日志。默认试跑回滚。"""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import socket
import sys
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    assert socket.gethostname().upper() == "PC" and ROOT == Path(r"E:\xinshi_system")
    assert Path(sys.executable).resolve() == (ROOT / r".venv\Scripts\python.exe").resolve()
    from import_resource_development_20261026 import SOURCE, EXPECTED_SHA, BATCH, backup
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_SHA
    import main as app_models  # noqa: F401
    from database import SessionLocal, engine
    from models import AppUser
    from resource_models import ResourcePerson
    from resource_development_models import DevelopmentAudit as Audit, DevelopmentCounter as Counter, DevelopmentRecord as Record
    from resource_development_import_preview import source_values
    from resource_development_service import lock_writes, refresh_draft, snapshot
    from business_time import business_now, business_iso

    assert engine.url.host == "43.132.156.72" and engine.url.port == 15432 and engine.url.database == "xinshi_system"
    if args.apply:
        assert args.backup_dir and args.backup_dir.is_dir()
        backup(engine, args.backup_dir)
    ids = {uuid5(NAMESPACE_URL, f"{BATCH}:record:{row}"): row for row in range(2874, 2887)}
    report = {"source_sha256": EXPECTED_SHA, "batch": BATCH, "apply": args.apply,
              "started_at": business_iso(business_now()), "backup": str(args.backup_dir) if args.apply else None,
              "quarantined_rows": []}
    with SessionLocal() as db:
        lock_writes(db)
        actor = db.query(AppUser).filter_by(username="zhengran", is_active=True).one()
        talents_before = db.query(ResourcePerson).count()
        records = db.query(Record).filter(Record.id.in_(list(ids))).order_by(Record.work_date).all()
        assert len(records) == 13, "待撤回的记录数量不符"
        affected = set()
        counter_keys = set()
        now = business_now()
        for record in records:
            source_row = ids[record.id]
            source = source_values(record)
            assert record.historical_only and record.person_id is None
            assert source and str(source["日期"]) == f"202610{source_row - 2847}"
            assert record.work_date > date(2026, 10, 26) and record.work_date <= date(2026, 11, 8)
            assert BATCH in record.remarks and f'"rows": [{source_row}]' in record.remarks
            report["quarantined_rows"].append({"source_row": source_row, "id": str(record.id),
                                                "raw_date": str(source["日期"]), "assigned_date": record.work_date.isoformat(),
                                                "source_values": source})
            affected.add((record.owner_id, record.work_date))
            counter_keys.add((record.platform_id, record.work_date))
            db.add(Audit(entity_id=record.id, entity_type="record", actor_id=actor.id, action="delete",
                         before=snapshot(record), after={}, created_at=now))
            db.delete(record)
        db.flush()
        for platform_id, work_date in counter_keys:
            if not db.query(Record.id).filter_by(platform_id=platform_id, work_date=work_date).first():
                counter = db.get(Counter, (platform_id, work_date))
                if counter:
                    db.delete(counter)
        db.flush()
        for owner_id, work_date in affected:
            refresh_draft(db, owner_id, work_date)
        db.flush()
        assert db.query(ResourcePerson).count() == talents_before
        assert db.query(Record).filter(Record.id.in_(list(ids))).count() == 0
        report["remaining_records"] = db.query(Record).count()
        report["finished_at"] = business_iso(business_now())
        if args.apply:
            db.commit()
        else:
            db.rollback()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"apply": args.apply, "removed": len(report["quarantined_rows"]),
                      "remaining_records": report["remaining_records"], "report": str(args.report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
