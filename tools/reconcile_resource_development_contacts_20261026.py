"""资源开拓原表联系方式分类回填。默认试跑回滚；--apply 前备份。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = Path(r"E:\Documents\william代码\管理系统资源\10.26资源开拓统筹.xlsx")
EXPECTED_SHA = "e87d276a5ec7f97d4244070e5f8197f43271074b64007231e366b2b7b3bc56ac"
BATCH = "resource-development-contact-reconcile-20261026-" + EXPECTED_SHA[:12]


def proposed_changes(record, raw, parsed):
    """仅补空值；只清除可证明由旧解析器误放的内容。"""
    before = {field: getattr(record, field) or "" for field in ("phone", "wechat", "xiaohongshu")}
    after = dict(before)
    conflicts = []
    xhs_only = parsed["kind"] == "xiaohongshu_labeled"
    if xhs_only and parsed["xiaohongshu"]:
        if after["wechat"] in {raw, parsed["xiaohongshu"]}:
            after["wechat"] = ""
        if not parsed["phone"] and after["phone"] == parsed["xiaohongshu"]:
            after["phone"] = ""
    if parsed["kind"] in {"missing_marker", "third_party", "other_channel", "wechat_display_name", "email_other", "person_name"}:
        if after["wechat"] == raw and not parsed["wechat"]:
            after["wechat"] = ""
    if parsed["kind"] == "person_name" and after["wechat"] == raw.split()[0]:
        after["wechat"] = ""
    if parsed["kind"] == "other_channel":
        if after["wechat"].casefold().startswith("whatsapp") and not parsed["wechat"]:
            after["wechat"] = ""
        if parsed["wechat"] and after["wechat"] in raw and after["wechat"].startswith("(+"):
            after["wechat"] = ""
        if parsed["wechat"] and "(WeChat)" in raw and after["phone"] == parsed["wechat"]:
            after["phone"] = ""
    if parsed["kind"] == "phone_with_note" and after["wechat"] == raw:
        after["wechat"] = ""
    if parsed["kind"] == "unclassified" and after["wechat"] == raw and any(char in raw for char in "“”添加时"):
        after["wechat"] = ""
    if parsed["kind"] == "wechat_labeled" and after["phone"] == parsed["wechat"]:
        after["phone"] = ""
    for field in ("phone", "wechat", "xiaohongshu"):
        expected = parsed[field]
        if not expected:
            continue
        if not after[field] or after[field] == raw:
            after[field] = expected
        elif after[field] != expected:
            conflicts.append(field)
    return {field: {"before": before[field], "after": after[field]} for field in before if before[field] != after[field]}, conflicts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    assert socket.gethostname().upper() == "PC" and ROOT == Path(r"E:\xinshi_system")
    assert Path(sys.executable).resolve() == (ROOT / r".venv\Scripts\python.exe").resolve()
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_SHA, "工作簿版本已变化"
    import main as app_models  # noqa: F401
    from database import SessionLocal, engine
    from models import AppUser
    from resource_models import ResourcePerson
    from resource_development_models import DevelopmentAudit as Audit, DevelopmentRecord as Record
    from resource_development_import_preview import cell, source_values
    from resource_development_contacts import classify_contact
    from resource_development_service import lock_writes, snapshot
    from business_time import business_now, business_iso
    from import_resource_development_20261026 import backup

    assert engine.url.host == "43.132.156.72" and engine.url.port == 15432 and engine.url.database == "xinshi_system"
    if args.apply:
        assert args.backup_dir and args.backup_dir.is_dir()
        backup(engine, args.backup_dir, BATCH)
    report = {"batch": BATCH, "source_sha256": EXPECTED_SHA, "apply": args.apply,
              "started_at": business_iso(business_now()), "backup": str(args.backup_dir) if args.apply else None,
              "counts": Counter(), "rows": [], "conflicts": [], "protected": []}
    with SessionLocal() as db:
        lock_writes(db)
        actor = db.query(AppUser).filter_by(username="zhengran", is_active=True).one()
        talents_before = db.query(ResourcePerson).count()
        now = business_now()
        for record in db.query(Record).all():
            source = source_values(record)
            if not source:
                continue
            raw = cell(source.get("备注：微信号/手机号"))
            if not raw:
                continue
            parsed = classify_contact(raw)
            report["counts"]["source_nonempty"] += 1
            report["counts"]["kind_" + parsed["kind"]] += 1
            if not record.historical_only or record.person_id is not None:
                report["protected"].append({"record_id": str(record.id), "raw": raw})
                continue
            changes, conflicts = proposed_changes(record, raw, parsed)
            if conflicts:
                report["conflicts"].append({"record_id": str(record.id), "raw": raw,
                                             "parsed": parsed, "fields": conflicts})
            if not changes:
                continue
            before = snapshot(record)
            for field, value in changes.items():
                setattr(record, field, value["after"])
                report["counts"]["field_" + field + "_changed"] += 1
                if not value["before"] and value["after"]:
                    report["counts"]["field_" + field + "_filled"] += 1
                if value["before"] and not value["after"]:
                    report["counts"]["field_" + field + "_cleared"] += 1
            record.updated_at = now
            record.updated_by = actor.id
            record.revision += 1
            db.add(Audit(entity_id=record.id, entity_type="record", actor_id=actor.id, action="update",
                         before=before, after=snapshot(record), created_at=now))
            report["rows"].append({"record_id": str(record.id), "raw": raw, "kind": parsed["kind"],
                                   "changes": changes})
        db.flush()
        assert db.query(ResourcePerson).count() == talents_before
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_SHA, "工作簿在试跑期间变化"
        report["counts"].update(records_changed=len(report["rows"]), conflicts=len(report["conflicts"]),
                                protected=len(report["protected"]), talents_before_after=talents_before)
        report["finished_at"] = business_iso(business_now())
        if args.apply:
            db.commit()
        else:
            db.rollback()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=dict), encoding="utf-8")
    print(json.dumps({"apply": args.apply, "counts": report["counts"], "report": str(args.report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
