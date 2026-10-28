"""10.26 资源开拓统筹增量导入。默认试跑回滚，--apply 提交。"""
import argparse
from collections import Counter, defaultdict
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
import re
import socket
import sys
from uuid import NAMESPACE_URL, UUID, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EXPECTED_SHA = "03f023c9d6503334cc362d1e42168c3efe6aa2926673cd45e804c489bf7d0625"
SOURCE = Path(r"E:\Documents\william代码\管理系统资源\10.26资源开拓统筹.xlsx")
BATCH = "resource-development-20261026-" + EXPECTED_SHA[:12]
TABLES = (
    "resource_development_record", "resource_development_action", "resource_development_follow_up",
    "resource_development_language", "resource_development_option", "resource_development_counter",
    "resource_development_audit", "daily_report", "daily_report_item",
)


def backup(engine, folder, batch=BATCH):
    """同一个只读快照备份所有可能被这批次改动的表。"""
    if any(folder.iterdir()):
        raise RuntimeError("备份目录必须为空")
    manifest = {"batch": batch, "tables": {}, "database": "xinshi_system"}
    connection = engine.raw_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        for table in TABLES:
            target = folder / f"{table}.csv.gz"
            with gzip.open(target, "wt", encoding="utf-8", newline="") as stream:
                cursor.copy_expert(f"COPY {table} TO STDOUT WITH (FORMAT CSV, HEADER TRUE)", stream)
            manifest["tables"][table] = {"bytes": target.stat().st_size, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
        connection.rollback()
    finally:
        connection.close()
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def business_day(raw, source_row, parse_date):
    if 2874 <= source_row <= 2886 and str(raw) == f"202610{source_row - 2847}":
        # 用户确认：表尾自动递增的 13 行实际均属于 10 月 26 日。
        return date(2026, 10, 26)
    parsed = parse_date(raw)
    if parsed:
        day = date.fromisoformat(parsed)
        if day <= date(2026, 10, 26):
            return day
    raise ValueError(f"第 {source_row} 行日期超出 10 月 26 日快照或无效：{raw!r}")


def staging_record_id(source_row):
    suffix = f"corrected-20261026:record:{source_row}" if 2874 <= source_row <= 2886 else f"record:{source_row}"
    return uuid5(NAMESPACE_URL, f"{BATCH}:{suffix}")


def split_contact(value):
    from resource_development_contacts import classify_contact
    parsed = classify_contact(value)
    return parsed["phone"], parsed["wechat"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    assert socket.gethostname().upper() == "PC" and ROOT == Path(r"E:\xinshi_system"), "只能在已确认的 PC 项目目录执行"
    assert Path(sys.executable).resolve() == (ROOT / r".venv\Scripts\python.exe").resolve(), "必须使用项目 .venv"
    content = SOURCE.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    assert digest == EXPECTED_SHA, "源文件哈希发生变化"
    if args.apply:
        assert args.backup_dir and args.backup_dir.is_dir(), "提交前必须指定已加固的备份目录"

    import main as app_models  # noqa: F401 载入所有模型映射
    from database import SessionLocal, engine
    from sqlalchemy import text
    from models import AppUser
    from interpretation_models import InterpretationLanguage
    from resource_models import ResourcePerson
    from resource_development_models import (
        DevelopmentAction as Action, DevelopmentAudit as Audit, DevelopmentCounter as DbCounter,
        DevelopmentFollowUp as FollowUp, DevelopmentLanguage as Language,
        DevelopmentOption as Option, DevelopmentRecord as Record,
    )
    from resource_development_import_preview import (
        HEADERS, OWNER_ALIASES, PLATFORM_ALIASES, action_preview, cell, key,
        match_languages, parse_date, preview_workbook, source_values,
    )
    from resource_development_service import lock_writes, progress_status, refresh_draft, snapshot
    from business_time import business_now, business_iso

    url = engine.url
    assert url.host == "43.132.156.72" and url.port == 15432 and url.database == "xinshi_system", "数据库目标不符"
    with engine.connect() as connection:
        assert connection.execute(text("select current_database() ")).scalar() == "xinshi_system"
    if args.apply:
        backup_manifest = backup(engine, args.backup_dir)
    else:
        backup_manifest = None

    report = {"batch": BATCH, "source_sha256": digest, "apply": args.apply, "started_at": business_iso(business_now()),
              "backup": str(args.backup_dir) if args.apply else None, "backup_tables": len(backup_manifest["tables"]) if backup_manifest else 0,
              "counts": Counter(), "inferences": [], "unmapped": [], "loose_matches": []}
    with SessionLocal() as db:
        lock_writes(db)
        preview = preview_workbook(content, db)
        assert preview["total"] == 2885, "源表行数有变化"
        users = db.query(AppUser).all()
        names = {item.full_name or item.username: item for item in users}
        names.update({short: names[full] for short, full in OWNER_ALIASES.items() if full in names})
        names.update({"以龙": names["郭以龙"], "晨旭": names["习晨旭"], "李珈": names["沈政燃"]})
        actor = next((item for item in users if item.username == "zhengran"), None)
        assert actor and actor.is_active
        options = {(item.kind, item.name.casefold()): item for item in db.query(Option).all()}
        languages = {item.label: item for item in db.query(InterpretationLanguage).filter_by(is_active=True).all()}
        existing = db.query(Record).all()
        existing_record_ids = {item.id for item in existing}
        old_by_key = defaultdict(list)
        loose = defaultdict(list)
        for item in existing:
            old = source_values(item)
            if old:
                old_by_key[key(old)].append(item)
            loose[(item.work_date, item.owner_id, item.full_name.strip().casefold())].append(item)
        counters = {(item.platform_id, item.work_date): item for item in db.query(DbCounter).all()}
        before_talents = db.query(ResourcePerson).count()
        now = business_now()
        grouped = defaultdict(list)
        for row in preview["rows"]:
            raw_date = row["values"]["日期"]
            parsed_date = parse_date(raw_date)
            if 2874 <= row["row"] <= 2886 and raw_date == f"202610{row['row'] - 2847}":
                report.setdefault("date_corrections", []).append({"row": row["row"], "raw_date": raw_date,
                                                                   "confirmed_date": "2026-10-26", "basis": "用户确认"})
            elif not parsed_date or date.fromisoformat(parsed_date) > date(2026, 10, 26):
                raise ValueError(f"第 {row['row']} 行日期不能作为 10 月 26 日快照导入：{raw_date}")
            grouped[key(row["values"])].append(row)
        report["counts"]["source_rows"] = preview["total"]
        report["counts"]["source_groups"] = len(grouped)
        report["counts"]["corrected_date_rows"] = len(report.get("date_corrections", []))
        assert report["counts"]["corrected_date_rows"] == 13
        touched = set()
        created_records = []
        pending_children = []
        before_by_record = {}
        touched_records = {}
        existing_action_keys = {(item.record_id, item.channel, item.status, item.action_date, item.operator_id)
                                for item in db.query(Action).all()}
        existing_action_ids = {item.id for item in db.query(Action.id).all()}
        existing_followup_ids = {item.id for item in db.query(FollowUp.id).all()}
        existing_language_keys = {(item.record_id, item.language_id) for item in db.query(Language).all()}

        for option_name in ("HR7微信", "HR3"):
            if ("account", option_name.casefold()) not in options:
                created_option = Option(kind="account", category="", name=option_name, code=None,
                                        description="10.26资源开拓统筹原表账号", created_by=actor.id, updated_by=actor.id,
                                        created_at=now, updated_at=now)
                db.add(created_option)
                db.flush()
                options[("account", option_name.casefold())] = created_option
                report["counts"]["account_options_created"] += 1

        for group in grouped.values():
            first = group[0]
            values = first["values"]
            source_rows = [row["row"] for row in group]
            day = business_day(values["日期"], first["row"], parse_date)
            raw_owner = values["开拓人/HR"]
            owner = names.get(raw_owner) or names.get(OWNER_ALIASES.get(raw_owner, ""))
            assert owner, f"第 {first['row']} 行开拓人仍无法匹配：{raw_owner}"
            platform_name = PLATFORM_ALIASES.get(values["来源"].casefold(), values["来源"])
            platform = options.get(("platform", platform_name.casefold())) or options.get(("platform", "来源待确认"))
            assert platform and platform.code, f"第 {first['row']} 行平台无法映射"
            account_raw = values["对接账号"]
            account_name = "HR7微信" if re.fullmatch(r"(?i)hr7微信", account_raw) else "WhatsApp" if account_raw.casefold() == "hr3 whatsapp" else account_raw
            account = options.get(("account", account_name.casefold()))
            if not account and account_name:
                account = options.get(("account", re.sub(r"微信$", "", account_name).casefold()))
            if account_raw and not account:
                report["unmapped"].append({"row": first["row"], "field": "对接账号", "raw": account_raw})
            phone, wechat = split_contact(values["备注：微信号/手机号"])
            from resource_development_contacts import classify_contact
            xiaohongshu = classify_contact(values["备注：微信号/手机号"])["xiaohongshu"]
            matches = old_by_key.get(key(values), [])
            assert len(matches) <= 1, f"第 {first['row']} 行历史匹配不唯一"
            record = matches[0] if matches else None
            if not record:
                candidates = loose.get((day, owner.id, values["姓名"].strip().casefold()), [])
                if candidates:
                    confirmed = [item for item in candidates if (phone and item.phone == phone) or (wechat and item.wechat == wechat)]
                    if len(confirmed) == 1 and confirmed[0].historical_only:
                        record = confirmed[0]
                        report["loose_matches"].append({"row": first["row"], "id": str(record.id), "basis": "日期、开拓人、姓名、联系方式"})
                    else:
                        report["loose_matches"].append({"row": first["row"], "candidate_ids": [str(x.id) for x in candidates], "basis": "仅同日同名，另建独立记录"})
            if record:
                if not record.historical_only or record.person_id is not None:
                    report["loose_matches"].append({"row": first["row"], "id": str(record.id), "basis": "已有正式记录，保持原状"})
                    report["counts"]["existing_protected_groups"] += 1
                    continue
                report["counts"]["existing_groups"] += 1
                before = snapshot(record)
                before_by_record.setdefault(record.id, before)
                if account and record.account_id is None:
                    record.account_id = account.id
                    record.updated_by = actor.id
                    record.updated_at = now
                    record.revision += 1
                    report["counts"]["existing_accounts_filled"] += 1
                source_block = f"【{BATCH}】" + json.dumps({"rows": source_rows, "values": [x["values"] for x in group]}, ensure_ascii=False)
                if source_block not in (record.remarks or ""):
                    record.remarks = (record.remarks or "") + "\n" + source_block
                    record.updated_by = actor.id
                    record.updated_at = now
                    record.revision += 1
                    report["counts"]["existing_updated"] += 1
                else:
                    report["counts"]["existing_already_imported"] += 1
            else:
                rid = staging_record_id(source_rows[0])
                assert rid not in existing_record_ids, "确定性记录 ID 已存在但未匹配源表"
                counter_key = (platform.id, day)
                counter = counters.get(counter_key)
                if not counter:
                    counter = DbCounter(platform_id=platform.id, work_date=day, value=0)
                    db.add(counter)
                    counters[counter_key] = counter
                counter.value += 1
                greeting = f"{platform.code}-{day:%y%m%d}-{counter.value:03d}"
                raw_block = "【原表信息】" + json.dumps(values, ensure_ascii=False)
                batch_block = f"【{BATCH}】" + json.dumps({"rows": source_rows, "values": [x["values"] for x in group]}, ensure_ascii=False)
                notes = [raw_block, batch_block]
                if raw_owner == "李珈":
                    notes.append("【开拓人推断】原表李珈；沿用历史映射到沈政燃")
                if 2874 <= source_rows[0] <= 2886:
                    notes.append(f"【日期更正】原表{values['日期']}；用户确认实际为2026-10-26")
                if platform.name != platform_name:
                    notes.append(f"【原来源】{values['来源']}")
                if account_raw and not account:
                    notes.append(f"【未映射对接账号】{account_raw}")
                if values["备注：微信号/手机号"]:
                    notes.append(f"【原联系方式】{values['备注：微信号/手机号']}")
                markers = {field: {"raw": values[field]} for field in ("已加微信", "已加企微", "已邀进群", "已沟通", "已入项") if values[field]}
                record = Record(id=rid, greeting_no=greeting, platform_id=platform.id, work_date=day,
                                owner_id=owner.id, full_name=values["姓名"][:255], account_id=account.id if account else None,
                                phone=phone, wechat=wechat, xiaohongshu=xiaohongshu, follow_up="", remarks="\n".join(notes),
                                historical_only=True, historical_markers=markers, person_id=None,
                                created_by=actor.id, updated_by=actor.id, created_at=now, updated_at=now, revision=1)
                db.add(record)
                existing_record_ids.add(rid)
                created_records.append(record)
                loose[(day, owner.id, values["姓名"].strip().casefold())].append(record)
                report["counts"]["created_groups"] += 1
                before = None
            matched, unmatched = match_languages(values["语种"], languages)
            for label in matched:
                lang = languages[label]
                lk = (record.id, lang.id)
                if lk not in existing_language_keys:
                    pending_children.append(Language(record_id=record.id, language_id=lang.id))
                    existing_language_keys.add(lk)
                    report["counts"]["language_links_created"] += 1
            if unmatched:
                report["unmapped"].append({"row": first["row"], "field": "语种", "raw": unmatched})
                note = "【未映射语种原文】" + "、".join(unmatched)
                if note not in record.remarks:
                    record.remarks += "\n" + note
            for row in group:
                row_values = row["values"]
                for field in ("已加微信", "已加企微", "已邀进群", "已沟通", "已入项"):
                    raw = row_values[field]
                    if not raw:
                        continue
                    action = action_preview(raw, field, day.isoformat(), names)
                    operator = names.get(action["operator"])
                    if not action["date"] or not operator or not action["status"]:
                        report["counts"]["unparsed_action_cells"] += 1
                        continue
                    action_day = date.fromisoformat(action["date"])
                    action_key = (record.id, action["channel"], action["status"], action_day, operator.id)
                    if action_key in existing_action_keys:
                        continue
                    aid = uuid5(NAMESPACE_URL, f"{BATCH}:action:{record.id}:{field}:{raw}")
                    if aid not in existing_action_ids:
                        pending_children.append(Action(id=aid, record_id=record.id, channel=action["channel"], status=action["status"],
                                      request_number=0, action_date=action_day, operator_id=operator.id,
                                      account_id=account.id if account else None, created_by=actor.id, updated_by=actor.id,
                                      created_at=now, updated_at=now))
                        report["counts"]["actions_created"] += 1
                        existing_action_ids.add(aid)
                    existing_action_keys.add(action_key)
                follow = row_values["后续跟进情况"]
                if follow:
                    content_text = f"【10.26统筹表第{row['row']}行】{follow}"
                    fid = uuid5(NAMESPACE_URL, f"{BATCH}:follow:{record.id}:{row['row']}:{follow}")
                    if fid not in existing_followup_ids:
                        pending_children.append(FollowUp(id=fid, record_id=record.id, content=content_text, operator_id=actor.id, created_at=now))
                        existing_followup_ids.add(fid)
                        report["counts"]["followups_created"] += 1
            touched.add((owner.id, day))
            touched_records[record.id] = record
        db.flush()
        db.add_all(pending_children)
        db.flush()
        actions_by_record = defaultdict(list)
        for action in db.query(Action).filter(Action.record_id.in_(list(touched_records))).order_by(Action.created_at, Action.id):
            actions_by_record[action.record_id].append(action)
        for record in touched_records.values():
            actions = actions_by_record[record.id]
            if record.account_id and record.id in before_by_record and before_by_record[record.id].get("account_id") is None:
                for action in actions:
                    if action.account_id is None:
                        action.account_id = record.account_id
            for channel, field in (("wechat", "wechat_status"), ("enterprise", "enterprise_status")):
                count = 0
                current = (record.historical_markers or {}).get(channel, {}).get("status", "未处理")
                for action in (item for item in actions if item.channel == channel):
                    status = progress_status(action.status, channel)
                    if status in {"一次请求", "二次请求", "三次请求"}:
                        count = max(count + 1, {"二次请求": 2, "三次请求": 3}.get(status, 1))
                        action.request_number = count
                    else:
                        action.request_number = 0
                    current = action.status
                setattr(record, field, current)
        db.flush()
        db.add_all([Audit(entity_id=item.id, entity_type="record", actor_id=actor.id, action="create",
                          before={}, after=snapshot(item), created_at=now) for item in created_records])
        db.add_all([Audit(entity_id=record_id, entity_type="record", actor_id=actor.id, action="update",
                          before=before, after=snapshot(touched_records[record_id]), created_at=now)
                    for record_id, before in before_by_record.items() if before != snapshot(touched_records[record_id])])
        db.add_all([Audit(entity_id=item.id, entity_type=item.__tablename__.removeprefix("resource_development_"),
                          actor_id=actor.id, action="create", before={}, after=snapshot(item), created_at=now)
                    for item in pending_children if isinstance(item, (Action, FollowUp))])
        for owner_id, day in touched:
            refresh_draft(db, owner_id, day)
        db.flush()
        assert db.query(ResourcePerson).count() == before_talents, "人才总库数量异常变化"
        assert report["counts"]["created_groups"] + report["counts"]["existing_groups"] + report["counts"]["existing_protected_groups"] == len(grouped)
        assert all(item.person_id is None for item in db.query(Record).filter(Record.id.in_([staging_record_id(group[0]["row"]) for group in grouped.values()])).all())
        report["counts"]["touched_owner_days"] = len(touched)
        report["counts"]["talents_before_after"] = before_talents
        report["finished_at"] = business_iso(business_now())
        if args.apply:
            db.commit()
        else:
            db.rollback()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=dict), encoding="utf-8")
    print(json.dumps({"apply": args.apply, "counts": report["counts"], "report": str(args.report), "backup": report["backup"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
