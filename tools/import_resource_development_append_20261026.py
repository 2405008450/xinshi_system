"""补录 10.26 工作簿新追加的第 2887～2925 行；默认试跑回滚。"""
import argparse
from collections import Counter
from datetime import date
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import socket
import sys
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = Path(r"E:\Documents\william代码\管理系统资源\10.26资源开拓统筹.xlsx")
EXPECTED_SHA = "e87d276a5ec7f97d4244070e5f8197f43271074b64007231e366b2b7b3bc56ac"
BATCH = "resource-development-20261026-append-" + EXPECTED_SHA[:12]


def match_extra_languages(raw, catalog):
    from resource_development_import_preview import match_languages
    matched, unmatched = match_languages(raw, catalog)
    unresolved = []
    for part in unmatched:
        value = part.replace("母语者", "").replace("母语", "").replace("和", "、").replace("及", "、")
        for segment in re.split(r"[、\s]+", value):
            if not segment:
                continue
            if segment in catalog:
                matched.append(segment)
                continue
            remaining = segment
            found = []
            for label in sorted(catalog, key=len, reverse=True):
                if label in remaining:
                    remaining = remaining.replace(label, "", 1)
                    found.append(label)
            matched.extend(found)
            if remaining:
                unresolved.append(segment)
    return list(dict.fromkeys(matched)), list(dict.fromkeys(unresolved))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    assert socket.gethostname().upper() == "PC" and ROOT == Path(r"E:\xinshi_system")
    assert Path(sys.executable).resolve() == (ROOT / r".venv\Scripts\python.exe").resolve()
    content = SOURCE.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    assert digest == EXPECTED_SHA, "工作簿仍在变化，先暂停导入"
    import main as app_models  # noqa: F401
    from openpyxl import load_workbook
    from database import SessionLocal, engine
    from models import AppUser
    from resource_models import ResourcePerson
    from interpretation_models import InterpretationLanguage
    from resource_development_models import (
        DevelopmentAudit as Audit, DevelopmentCounter as DbCounter, DevelopmentLanguage as Language,
        DevelopmentOption as Option, DevelopmentRecord as Record,
    )
    from resource_development_import_preview import HEADERS, OWNER_ALIASES, PLATFORM_ALIASES, cell, key, source_values
    from resource_development_service import lock_writes, refresh_draft, snapshot
    from business_time import business_now, business_iso
    from import_resource_development_20261026 import backup, split_contact
    from resource_development_contacts import classify_contact

    assert engine.url.host == "43.132.156.72" and engine.url.port == 15432 and engine.url.database == "xinshi_system"
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    assert tuple(cell(x) for x in next(workbook.active.values)[:13]) == HEADERS
    rows = []
    for row_number, raw in enumerate(workbook.active.values, 1):
        if 2887 <= row_number <= 2925:
            values = dict(zip(HEADERS, [cell(x) for x in raw[:13]]))
            assert any(values.values()), f"第 {row_number} 行为空"
            assert values["日期"] == "20261026", f"第 {row_number} 行日期异常"
            assert values["姓名"], f"第 {row_number} 行姓名为空"
            assert all(not values[field] for field in HEADERS[7:]), f"第 {row_number} 行有未处理动作或跟进"
            rows.append((row_number, values))
    workbook.close()
    assert len(rows) == 39
    assert len({key(values) for _, values in rows}) == 39, "追加行内存在重复候选"
    if args.apply:
        assert args.backup_dir and args.backup_dir.is_dir()
        backup(engine, args.backup_dir, BATCH)
    report = {"batch": BATCH, "source_sha256": digest, "apply": args.apply,
              "started_at": business_iso(business_now()), "backup": str(args.backup_dir) if args.apply else None,
              "created": [], "already_present": [], "unmapped_languages": [], "counts": Counter()}
    with SessionLocal() as db:
        lock_writes(db)
        actor = db.query(AppUser).filter_by(username="zhengran", is_active=True).one()
        users = {item.full_name or item.username: item for item in db.query(AppUser).all()}
        users.update({short: users[full] for short, full in OWNER_ALIASES.items() if full in users})
        users["晨旭"] = users["习晨旭"]
        options = {(item.kind, item.name.casefold()): item for item in db.query(Option).all()}
        languages = {item.label: item for item in db.query(InterpretationLanguage).filter_by(is_active=True).all()}
        counters = {(item.platform_id, item.work_date): item for item in db.query(DbCounter).all()}
        existing = db.query(Record).filter_by(work_date=date(2026, 10, 26)).all()
        old_by_key = {key(source_values(item)): item for item in existing if source_values(item)}
        now = business_now()
        talents_before = db.query(ResourcePerson).count()
        new_records, links, touched = [], [], set()
        for row_number, values in rows:
            owner = users.get(values["开拓人/HR"])
            assert owner, f"第 {row_number} 行开拓人无法映射"
            platform_name = PLATFORM_ALIASES.get(values["来源"].casefold(), values["来源"])
            platform = options.get(("platform", platform_name.casefold()))
            assert platform and platform.code, f"第 {row_number} 行来源无法映射"
            raw_account = values["对接账号"]
            account = options.get(("account", raw_account.casefold())) or options.get(("account", re.sub(r"微信$", "", raw_account).casefold()))
            assert account, f"第 {row_number} 行对接账号无法映射"
            phone, wechat = split_contact(values["备注：微信号/手机号"])
            xiaohongshu = classify_contact(values["备注：微信号/手机号"])["xiaohongshu"]
            rid = uuid5(NAMESPACE_URL, f"{BATCH}:record:{row_number}")
            old = db.get(Record, rid) or old_by_key.get(key(values))
            if not old:
                old = next((item for item in existing if item.owner_id == owner.id and item.full_name.strip().casefold() == values["姓名"].strip().casefold()
                            and ((phone and item.phone == phone) or (wechat and item.wechat == wechat))), None)
            if old:
                assert old.historical_only and old.person_id is None
                report["already_present"].append({"row": row_number, "record_id": str(old.id)})
                continue
            counter_key = (platform.id, date(2026, 10, 26))
            counter = counters.get(counter_key)
            if not counter:
                counter = DbCounter(platform_id=platform.id, work_date=date(2026, 10, 26), value=0)
                db.add(counter)
                counters[counter_key] = counter
            counter.value += 1
            matched, unmatched = match_extra_languages(values["语种"], languages)
            if unmatched:
                report["unmapped_languages"].append({"row": row_number, "raw": values["语种"], "unmatched": unmatched})
            notes = ["【原表信息】" + json.dumps(values, ensure_ascii=False),
                     f"【{BATCH}】第{row_number}行；原语种：{values['语种']}；原账号：{raw_account}；原联系方式：{values['备注：微信号/手机号']}"]
            if unmatched:
                notes.append("【未映射语种原文】" + "、".join(unmatched))
            record = Record(id=rid, greeting_no=f"{platform.code}-261026-{counter.value:03d}",
                            platform_id=platform.id, work_date=date(2026, 10, 26), owner_id=owner.id,
                            full_name=values["姓名"][:255], account_id=account.id, phone=phone, wechat=wechat, xiaohongshu=xiaohongshu,
                            follow_up="", remarks="\n".join(notes), historical_only=True, historical_markers={},
                            person_id=None, created_by=actor.id, updated_by=actor.id,
                            created_at=now, updated_at=now, revision=1)
            db.add(record)
            new_records.append(record)
            for label in matched:
                links.append(Language(record_id=rid, language_id=languages[label].id))
            report["created"].append({"row": row_number, "record_id": str(rid), "name": values["姓名"]})
            touched.add((owner.id, date(2026, 10, 26)))
        db.flush()
        db.add_all(links)
        db.add_all([Audit(entity_id=item.id, entity_type="record", actor_id=actor.id,
                          action="create", before={}, after=snapshot(item), created_at=now) for item in new_records])
        for owner_id, work_date in touched:
            refresh_draft(db, owner_id, work_date)
        db.flush()
        assert db.query(ResourcePerson).count() == talents_before
        assert len(report["created"]) + len(report["already_present"]) == 39
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_SHA, "工作簿在试跑期间变化"
        report["counts"].update(source_rows=39, created=len(report["created"]), already_present=len(report["already_present"]),
                                language_links=len(links), unmapped_language_rows=len(report["unmapped_languages"]),
                                talents_before_after=talents_before)
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
