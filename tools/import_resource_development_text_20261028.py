"""导入 10 月 26/27 日追加的开拓日志文本；默认试跑并回滚。"""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import socket
import sys
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = Path(r"E:\Documents\resource_development_20261028_addendum.txt")
EXPECTED_SHA = "0b6c331c207946dce74d60e5a14dd767c300840f81a362ff3ee9bc2f46f40b1c"
BATCH = "resource-development-text-20261028-" + EXPECTED_SHA[:12]


def parse_rows(content, headers):
    import io
    lines = list(csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), delimiter="\t"))
    assert len(lines) == 172 and all(len(row) == 14 and not row[13] for row in lines)
    assert Counter(row[0] for row in lines) == {"20261026": 58, "20261027": 114}
    rows = []
    for number, raw in enumerate(lines, 1):
        values = dict(zip(headers, (value.strip() for value in raw[:13])))
        assert values["姓名"] and values["开拓人/HR"] and values["来源"]
        assert all(not values[field] for field in headers[7:]), f"第 {number} 行有未处理的进度内容"
        rows.append((number, values))
    return rows


def matched_languages(raw, catalog):
    from import_resource_development_append_20261026 import match_extra_languages
    aliases = {"客家": "客家话", "潮汕": "潮汕话"}
    cleaned = re.sub(r"[&＆]", "、", raw)
    cleaned = "、".join(aliases.get(part.strip(), part.strip()) for part in re.split(r"[、，]", cleaned))
    return match_extra_languages(cleaned, catalog)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    assert socket.gethostname().upper() == "PC" and ROOT == Path(r"E:\xinshi_system")
    assert Path(sys.executable).resolve() == (ROOT / r".venv\Scripts\python.exe").resolve()
    content = SOURCE.read_bytes()
    assert hashlib.sha256(content).hexdigest() == EXPECTED_SHA, "追加文本发生变化"

    import main as app_models  # noqa: F401 加载完整 ORM 映射
    from sqlalchemy import text
    from database import SessionLocal, engine
    from models import AppUser
    from interpretation_models import InterpretationLanguage
    from resource_models import ResourcePerson
    from resource_development_models import (
        DevelopmentAudit as Audit, DevelopmentCounter as DbCounter, DevelopmentLanguage as Language,
        DevelopmentOption as Option, DevelopmentRecord as Record,
    )
    from resource_development_import_preview import HEADERS, OWNER_ALIASES, PLATFORM_ALIASES, key, source_values
    from resource_development_contacts import classify_contact
    from resource_development_service import lock_writes, refresh_draft, snapshot
    from business_time import business_now, business_iso
    from import_resource_development_20261026 import backup

    rows = parse_rows(content, HEADERS)
    assert len({key(values) for _, values in rows}) == 172, "追加文本含完全重复行"
    assert (engine.url.host, engine.url.port, engine.url.database) == ("43.132.156.72", 15432, "xinshi_system")
    with engine.connect() as connection:
        assert connection.execute(text("select current_database()")).scalar_one() == "xinshi_system"
    backup_manifest = None
    if args.apply:
        assert args.backup_dir and args.backup_dir.is_dir()
        backup_manifest = backup(engine, args.backup_dir, BATCH)

    report = {"batch": BATCH, "source": str(SOURCE), "source_sha256": EXPECTED_SHA,
              "apply": args.apply, "started_at": business_iso(business_now()),
              "backup": str(args.backup_dir) if args.apply else None,
              "backup_tables": len(backup_manifest["tables"]) if backup_manifest else 0,
              "counts": Counter(), "created": [], "already_present": [], "unmapped_languages": []}
    with SessionLocal() as db:
        lock_writes(db)
        actor = db.query(AppUser).filter_by(username="zhengran", is_active=True).one()
        users = {user.full_name or user.username: user for user in db.query(AppUser).all()}
        users.update({short: users[full] for short, full in OWNER_ALIASES.items() if full in users})
        options = {(option.kind, option.name.casefold()): option for option in db.query(Option).all()}
        catalog = {lang.label: lang for lang in db.query(InterpretationLanguage).filter_by(is_active=True).all()}
        counters = {(counter.platform_id, counter.work_date): counter for counter in db.query(DbCounter).all()}
        existing = db.query(Record).filter(Record.work_date.in_([date(2026, 10, 26), date(2026, 10, 27)])).all()
        by_source_key = defaultdict(list)
        by_person_day = defaultdict(list)
        for record in existing:
            original = source_values(record)
            if original:
                by_source_key[key(original)].append(record)
            by_person_day[(record.work_date, record.owner_id, record.full_name.strip().casefold())].append(record)
        now = business_now()
        talent_count = db.query(ResourcePerson).count()
        new_records, language_links, touched = [], [], set()

        for source_line, values in rows:
            day = date(int(values["日期"][:4]), int(values["日期"][4:6]), int(values["日期"][6:]))
            assert day in {date(2026, 10, 26), date(2026, 10, 27)}
            owner = users.get(values["开拓人/HR"])
            assert owner, f"第 {source_line} 行开拓人无法映射"
            platform_name = PLATFORM_ALIASES.get(values["来源"].casefold(), values["来源"])
            platform = options.get(("platform", platform_name.casefold()))
            assert platform and platform.code, f"第 {source_line} 行来源无法映射"
            account_raw = values["对接账号"]
            account = options.get(("account", account_raw.casefold()))
            if account is None:
                account = options.get(("account", re.sub(r"微信$", "", account_raw, flags=re.I).casefold()))
            assert account, f"第 {source_line} 行对接账号无法映射"
            contact = classify_contact(values["备注：微信号/手机号"])
            matched, unmatched = matched_languages(values["语种"], catalog)
            if unmatched:
                report["unmapped_languages"].append({"source_line": source_line, "raw": values["语种"], "unmatched": unmatched})

            rid = uuid5(NAMESPACE_URL, f"{BATCH}:record:{source_line}")
            old = db.get(Record, rid)
            if old is None:
                exact = by_source_key.get(key(values), [])
                assert len(exact) <= 1, f"第 {source_line} 行原文匹配不唯一"
                old = exact[0] if exact else None
            if old is None:
                candidates = by_person_day[(day, owner.id, values["姓名"].strip().casefold())]
                # 同日同名不足以合并；至少还须有相同的明确联系方式及来源。
                confirmed = [record for record in candidates if record.platform_id == platform.id and (
                    (contact["phone"] and record.phone == contact["phone"]) or
                    (contact["wechat"] and record.wechat == contact["wechat"]) or
                    (contact["xiaohongshu"] and record.xiaohongshu == contact["xiaohongshu"]))]
                assert len(confirmed) <= 1, f"第 {source_line} 行联系方式匹配不唯一"
                old = confirmed[0] if confirmed else None
            if old:
                assert old.work_date == day and old.owner_id == owner.id and old.full_name.strip().casefold() == values["姓名"].strip().casefold()
                report["already_present"].append({"source_line": source_line, "record_id": str(old.id), "name": values["姓名"]})
                report["counts"][f"already_present_{day.isoformat()}"] += 1
                continue

            counter_key = (platform.id, day)
            counter = counters.get(counter_key)
            if counter is None:
                counter = DbCounter(platform_id=platform.id, work_date=day, value=0)
                db.add(counter)
                counters[counter_key] = counter
            counter.value += 1
            notes = ["【原表信息】" + json.dumps(values, ensure_ascii=False),
                     "【追加文本来源】" + json.dumps({"batch": BATCH, "source_line": source_line,
                                                "source_sha256": EXPECTED_SHA}, ensure_ascii=False)]
            if account.name.casefold() != account_raw.casefold():
                notes.append(f"【原对接账号】{account_raw}")
            if values["备注：微信号/手机号"]:
                notes.append(f"【原联系方式】{values['备注：微信号/手机号']}")
            if unmatched:
                notes.append("【未映射语种原文】" + "、".join(unmatched))
            record = Record(id=rid, greeting_no=f"{platform.code}-{day:%y%m%d}-{counter.value:03d}",
                            platform_id=platform.id, work_date=day, owner_id=owner.id,
                            full_name=values["姓名"][:255], account_id=account.id,
                            phone=contact["phone"], wechat=contact["wechat"], xiaohongshu=contact["xiaohongshu"],
                            follow_up="", remarks="\n".join(notes), historical_only=True, historical_markers={},
                            person_id=None, created_by=actor.id, updated_by=actor.id,
                            created_at=now, updated_at=now, revision=1)
            db.add(record)
            new_records.append(record)
            by_person_day[(day, owner.id, values["姓名"].strip().casefold())].append(record)
            for label in matched:
                language_links.append(Language(record_id=rid, language_id=catalog[label].id))
            report["created"].append({"source_line": source_line, "record_id": str(rid),
                                      "work_date": day.isoformat(), "name": values["姓名"],
                                      "contact_kind": contact["kind"], "language_names": matched})
            report["counts"][f"created_{day.isoformat()}"] += 1
            touched.add((owner.id, day))

        db.flush()
        db.add_all(language_links)
        db.add_all([Audit(entity_id=record.id, entity_type="record", actor_id=actor.id,
                          action="create", before={}, after=snapshot(record), created_at=now)
                    for record in new_records])
        for owner_id, day in touched:
            refresh_draft(db, owner_id, day)
        db.flush()
        assert db.query(ResourcePerson).count() == talent_count
        assert len(report["created"]) + len(report["already_present"]) == 172
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_SHA
        report["counts"].update(source_rows=172, created=len(report["created"]),
                                already_present=len(report["already_present"]),
                                language_links=len(language_links),
                                unmapped_language_rows=len(report["unmapped_languages"]),
                                touched_owner_days=len(touched), talents_before_after=talent_count)
        report["finished_at"] = business_iso(business_now())
        if args.apply:
            db.commit()
        else:
            db.rollback()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"apply": args.apply, "counts": report["counts"],
                      "report": str(args.report), "backup": report["backup"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
