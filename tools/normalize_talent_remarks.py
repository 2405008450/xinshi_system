"""人才备注规范化：snapshot / preview（默认只读）/ apply / verify / rollback。

生产写入必须指定目标、已核验备份与计划 SHA256。个人资料仅保存于仓库外。
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.talent_remark_rules import (VERSION, CONTACT_FIELDS, TEXT_MAP, canonical,
    digest, plan_person, Languages, vacant)

PERSON = "resource_person"
WRITABLE = ("resource_language_skill", "resource_certificate", "resource_education_experience")
TABLES = (PERSON, *WRITABLE, "resource_person_attachment", "resource_capability",
          "resource_written_translation_profile", "resource_interpretation_profile",
          "resource_annotation_profile", "resource_annotation_language_skill", "resource_career_profile",
          "interpretation_language", "interpretation_language_alias")


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as file:
        file.write(canonical(value))
        file.flush()
        os.fsync(file.fileno())
    temp.replace(path)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def json_value(value):
    return json.loads(canonical(value))


def outside(path):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT): raise ValueError("含个人资料的输出必须位于仓库外")
    return path


def context(args):
    if socket.gethostname().upper() != "WIN-LOLJ8UHT2G5" or ROOT != Path(r"E:\xinshi_system"):
        raise RuntimeError("运行及数据库操作仅允许在指定局域网调试机")
    from database import engine
    if engine.url.host != args.expected_host or engine.url.database != args.expected_database:
        raise RuntimeError("实际数据库目标与指定目标不符")
    from sqlalchemy import MetaData, Table
    metadata = MetaData()
    tables = {name: Table(name, metadata, autoload_with=engine) for name in TABLES}
    return engine, tables


def rows(connection, table, identifier=None, lock=False):
    from sqlalchemy import select
    query = select(table)
    if identifier is not None:
        key = "id" if table.name == PERSON else "person_id"
        query = query.where(table.c[key] == typed(table.c[key], identifier))
    if lock: query = query.with_for_update()
    return sorted([json_value(dict(row)) for row in connection.execute(query).mappings()], key=lambda r: str(r.get("id", r.get("person_id"))))


def typed(column, value):
    if value is None: return None
    from sqlalchemy import Date, DateTime, Numeric, Uuid
    if isinstance(column.type, Uuid) and isinstance(value, str): return UUID(value)
    if isinstance(column.type, DateTime) and isinstance(value, str): return datetime.fromisoformat(value)
    if isinstance(column.type, Date) and isinstance(value, str): return date.fromisoformat(value)
    if isinstance(column.type, Numeric) and isinstance(value, str): return Decimal(value)
    return value


def values(table, data):
    return {k: typed(table.c[k], v) for k, v in data.items()}


def state(connection, tables, identifier, lock=False):
    person = rows(connection, tables[PERSON], identifier, lock)
    if len(person) != 1: raise ValueError("目标人才不存在或身份不唯一")
    return {"person": person[0], "relations": {name: rows(connection, tables[name], identifier, lock) for name in TABLES if name not in (PERSON, "interpretation_language", "interpretation_language_alias")}}


def batch_states(connection, tables, identifiers, lock=False):
    """批量读取完整档案，避免跨网数据库对每个人重复十余次往返。"""
    from sqlalchemy import select
    result = {str(i): {"person": None, "relations": {name: [] for name in TABLES if name not in (PERSON, "interpretation_language", "interpretation_language_alias")}} for i in identifiers}
    for name in (PERSON, *next(iter(result.values()))["relations"]):
        table = tables[name]
        key = "id" if name == PERSON else "person_id"
        order = table.c.id if "id" in table.c else table.c.person_id
        query = select(table).where(table.c[key].in_([typed(table.c[key], i) for i in identifiers])).order_by(order)
        if lock: query = query.with_for_update()
        for item in connection.execute(query).mappings():
            row = json_value(dict(item)); identifier = str(row[key])
            if name == PERSON: result[identifier]["person"] = row
            else: result[identifier]["relations"][name].append(row)
    if any(v["person"] is None for v in result.values()): raise ValueError("目标人才已被删除")
    return result


def make_snapshot(engine, tables, directory):
    from sqlalchemy import text
    directory = outside(directory)
    directory.mkdir(parents=True, exist_ok=False)
    # 取消继承权限，只给执行账号与 SYSTEM，禁止个人资料落入共享仓库。
    if os.name == "nt":
        identity = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True)
        sid = next(csv.reader(identity.splitlines()))[1]
        subprocess.run(["icacls", str(directory), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"], check=True, capture_output=True)
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as c, c.begin():
        c.execute(text("SET TRANSACTION READ ONLY"))
        snapshot = {"version": VERSION, "database": {"host": engine.url.host, "name": engine.url.database}, "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "tables": {name: rows(c, table) for name, table in tables.items()}, "limits": {column.name: column.type.length for column in tables[PERSON].columns if getattr(column.type, "length", None)}}
    atomic_json(directory / "snapshot.json", snapshot)
    # 整库逻辑备份，校验 pg_restore 清单后生成清单哈希；密码仅经子进程环境传递。
    dump = directory / "production-before.dump"
    env = os.environ.copy()
    env["PGPASSWORD"] = engine.url.password or ""
    env["PGCONNECT_TIMEOUT"] = "15"
    pg_bin = Path(r"C:\Program Files\PostgreSQL\18\bin")
    result = subprocess.run([str(pg_bin / "pg_dump.exe"), "--host", engine.url.host, "--port", str(engine.url.port or 5432), "--username", engine.url.username, "--dbname", engine.url.database, "--format=custom", "--file", str(dump)], env=env, capture_output=True)
    if result.returncode: raise RuntimeError("生产备份失败（详细错误不打印凭据）")
    checked = subprocess.run([str(pg_bin / "pg_restore.exe"), "--list", str(dump)], capture_output=True, check=True)
    # 解码全部备份数据到空设备，校验完整内容；不连接数据库、不执行恢复 SQL。
    subprocess.run([str(pg_bin / "pg_restore.exe"), "--file", os.devnull, str(dump)], capture_output=True, check=True)
    (directory / "backup-toc.txt").write_bytes(checked.stdout)
    toc = checked.stdout.decode("utf-8", errors="replace")
    if dump.stat().st_size < 1000 or any(name not in toc for name in (PERSON, *WRITABLE)):
        raise RuntimeError("备份目录清单缺少人才表")
    manifest = {"database": snapshot["database"], "snapshot_sha256": file_hash(directory / "snapshot.json"), "backup_sha256": file_hash(dump), "backup_bytes": dump.stat().st_size, "git_commit": snapshot["git_commit"]}
    atomic_json(directory / "backup-manifest.json", manifest)
    print(canonical({"people": len(snapshot["tables"][PERSON]), "backup_verified": True, "backup_bytes": manifest["backup_bytes"]}))


def file_hash(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""): sha.update(chunk)
    return sha.hexdigest()


def validate_record(record, tables=None):
    from resource_schemas import ResourcePersonCreate, LanguageSkillInput, CertificateInput, EducationExperienceInput
    allowed = set(TEXT_MAP.values()) | set(CONTACT_FIELDS) | {"remarks"}
    if not set(record["changes"]) <= allowed: raise ValueError("计划包含未授权字段")
    if str(record["before"]["person"]["id"]) != record["id"]: raise ValueError("计划人员身份不一致")
    for key in record["changes"]:
        if key != "remarks" and not vacant(record["before"]["person"].get(key)):
            raise ValueError("计划试图覆盖非空字段")
    payload = {"full_name": record["before"]["person"]["full_name"], **record["changes"]}
    ResourcePersonCreate.model_validate(payload)
    schemas = dict(zip(WRITABLE, (LanguageSkillInput, CertificateInput, EducationExperienceInput)))
    for item in record["adds"]:
        if item["table"] not in WRITABLE: raise ValueError("未授权关联表")
        if item["values"]["person_id"] != record["id"]: raise ValueError("关联归属错误")
        schemas[item["table"]].model_validate(item["values"])
    for item in record["updates"]:
        if item["table"] not in WRITABLE: raise ValueError("未授权关联表")
        before = next(x for x in record["before"]["relations"][item["table"]] if str(x["id"]) == item["id"])
        if any(not vacant(before.get(k)) for k in item["changes"]): raise ValueError("试图覆盖关联非空字段")
        if not set(item["changes"]) <= set(schemas[item["table"]].model_fields): raise ValueError("未授权关联字段")
        schemas[item["table"]].model_validate({**before, **item["changes"]})
    if tables:
        for name, data in [(PERSON, record["changes"]), *[(x["table"], x["values"]) for x in record["adds"]], *[(x["table"], x["changes"]) for x in record["updates"]]]:
            for key, value in data.items():
                column = tables[name].c[key]
                if value is not None and getattr(column.type, "length", None) and len(str(value)) > column.type.length:
                    raise ValueError("计划值超过实际数据库字段长度")


def build_plan(directory):
    directory = outside(directory)
    snapshot = read(directory / "snapshot.json")
    relations = {name: defaultdict(list) for name in TABLES if name not in (PERSON, "interpretation_language", "interpretation_language_alias")}
    for name in relations:
        for row in snapshot["tables"][name]: relations[name][str(row["person_id"])].append(row)
    languages = Languages(snapshot["tables"]["interpretation_language"], snapshot["tables"]["interpretation_language_alias"])
    records = []
    counts, fields, errors = Counter(), Counter(), []
    for person in snapshot["tables"][PERSON]:
        current = {name: relations[name][str(person["id"])] for name in relations}
        record = plan_person(person, current, languages, snapshot["limits"])
        try: validate_record(record)
        except ValueError as exc:
            errors.append({"id": record["id"], "reason": str(exc)})
            # 校验失败整条不写，保留计划候选供复核。
            record["validation_errors"] = str(exc)
        counts.update(x["status"] for x in record["decisions"])
        if record["changes"] or record["adds"] or record["updates"]:
            counts["people_with_changes"] += 1
            fields.update(record["changes"].keys())
            fields.update(x["table"] for x in record["adds"])
            fields.update(x["table"] + "." + k for x in record["updates"] for k in x["changes"])
        records.append(record)
    plan = {"version": VERSION, "database": snapshot["database"], "snapshot_sha256": file_hash(directory / "snapshot.json"), "catalog_sha256": digest({name: snapshot["tables"][name] for name in ("interpretation_language", "interpretation_language_alias")}), "git_commit": snapshot["git_commit"], "records": records, "summary": {"people": len(records), "decisions": dict(counts), "fields": dict(fields), "validation_errors": len(errors)}}
    atomic_json(directory / "plan.json", plan)
    atomic_json(directory / "preview-summary.json", {**plan["summary"], "plan_sha256": file_hash(directory / "plan.json")})
    atomic_json(directory / "validation-errors.json", errors)
    print(canonical({**plan["summary"], "plan_sha256": file_hash(directory / "plan.json")}))


def load_plan(directory, expected_hash):
    directory = outside(directory)
    if file_hash(directory / "plan.json") != expected_hash: raise ValueError("计划散列不一致")
    plan = read(directory / "plan.json")
    manifest = read(directory / "backup-manifest.json")
    if plan["version"] != VERSION or plan["database"] != manifest["database"]: raise ValueError("计划版本或备份目标不符")
    if file_hash(directory / "snapshot.json") != plan["snapshot_sha256"] or plan["snapshot_sha256"] != manifest["snapshot_sha256"]:
        raise ValueError("计划与备份快照不一致")
    if file_hash(directory / "production-before.dump") != manifest["backup_sha256"]: raise ValueError("生产备份损坏或已变化")
    return plan


def mutate(connection, tables, record):
    from sqlalchemy import update
    table = tables[PERSON]
    if record["changes"]:
        changes = values(table, record["changes"])
        changes["updated_at"] = datetime.now()
        connection.execute(update(table).where(table.c.id == typed(table.c.id, record["id"])).values(**changes))
    for item in record["updates"]:
        table = tables[item["table"]]
        connection.execute(update(table).where(table.c.id == typed(table.c.id, item["id"])).values(**values(table, item["changes"])))
    for item in record["adds"]:
        table = tables[item["table"]]
        connection.execute(table.insert().values(**values(table, item["values"])))


def expected_state(record, after):
    """完整比较，证明业务字段与已有关联未发生计划外变化。"""
    before = record["before"]
    person = {**before["person"], **record["changes"]}
    if record["changes"]: person["updated_at"] = after["person"]["updated_at"]
    if after["person"] != person: return False
    for name, old_rows in before["relations"].items():
        wanted = {str(x.get("id", x.get("person_id"))): dict(x) for x in old_rows}
        for item in record["updates"]:
            if item["table"] == name: wanted[item["id"]].update(item["changes"])
        actual = {str(x.get("id", x.get("person_id"))): x for x in after["relations"][name]}
        inserted = [x for x in record["adds"] if x["table"] == name]
        if set(actual) != set(wanted) | {x["values"]["id"] for x in inserted}: return False
        if any(actual[k] != v for k, v in wanted.items()): return False
        for item in inserted:
            if any(actual[item["values"]["id"]].get(k) != v for k, v in item["values"].items()): return False
    return True


def apply_plan(engine, tables, directory, plan):
    from sqlalchemy import text
    path = directory / "ledger.json"
    ledger = read(path) if path.exists() else {"plan_sha256": file_hash(directory / "plan.json"), "records": {}, "batches": []}
    if ledger["plan_sha256"] != file_hash(directory / "plan.json"): raise ValueError("已有账本属于不同计划")
    candidates = [r for r in plan["records"] if r["changes"] or r["adds"] or r["updates"]]
    # 写前恢复 prepared 账本：若提交已完成则采用其精确 after 快照，不重复执行。
    with engine.connect() as c:
        for identifier, entry in ledger["records"].items():
            if entry["status"] == "prepared":
                current = state(c, tables, identifier)
                if current == entry["after"]: entry["status"] = "committed"
                elif current == entry["before"]: entry["status"] = "retry"
                else: entry["status"] = "blocked_concurrent"
    atomic_json(path, ledger)
    for offset in range(0, len(candidates), 200):
        committed = []
        batch = candidates[offset:offset+200]
        with engine.connect() as c:
            with c.begin():
                if engine.dialect.name == "postgresql":
                    c.execute(text("SELECT pg_advisory_xact_lock(260930, 1)"))
                    c.execute(text("SET LOCAL idle_in_transaction_session_timeout = '300000'"))
                # 防止目录变更导致已经审核的语言 ID 语义变化。
                catalog = {name: rows(c, tables[name]) for name in ("interpretation_language", "interpretation_language_alias")}
                if digest(catalog) != plan["catalog_sha256"]: raise ValueError("语种目录已变化，需重新预览")
                active = [r for r in batch if ledger["records"].get(r["id"], {}).get("status") not in {"committed", "blocked_concurrent", "rolled_back"}]
                current_states = batch_states(c, tables, [r["id"] for r in active], lock=True) if active else {}
                mutated = []
                for record in active:
                    identifier = record["id"]
                    prior = ledger["records"].get(identifier)
                    if prior and prior["status"] in {"committed", "blocked_concurrent", "rolled_back"}: continue
                    try:
                        with c.begin_nested():
                            validate_record(record, tables)
                            if record.get("validation_errors"): raise ValueError("预览校验失败")
                            current = current_states[identifier]
                            if current != record["before"]:
                                ledger["records"][identifier] = {"status": "blocked_concurrent", "reason": "字段、身份或关联快照已变化"}
                                continue
                            mutate(c, tables, record)
                            mutated.append(record)
                    except Exception as exc:
                        ledger["records"][identifier] = {"status": "failed", "reason": type(exc).__name__}
                after_states = batch_states(c, tables, [r["id"] for r in mutated]) if mutated else {}
                for record in mutated:
                    identifier = record["id"]
                    after = after_states[identifier]
                    if not expected_state(record, after): raise ValueError("事务内核验存在计划外变化，整批回滚")
                    ledger["records"][identifier] = {"status": "prepared", "before": current_states[identifier], "after": after}
                    committed.append(identifier)
                # 在提交之前持久化精确变更前后快照，兼容提交成功后进程中断。
                atomic_json(path, ledger)
            for identifier in committed: ledger["records"][identifier]["status"] = "committed"
            ledger["batches"].append({"offset": offset, "committed": len(committed)})
            atomic_json(path, ledger)
        print(canonical({"batch_offset": offset, "committed": len(committed)}), flush=True)
    return ledger


def verify(engine, tables, directory, plan):
    from sqlalchemy import text
    ledger = read(directory / "ledger.json")
    report = {"verified": 0, "mismatches": [], "ledger_status": dict(Counter(x["status"] for x in ledger["records"].values()))}
    snapshot = read(directory / "snapshot.json")
    records = {r["id"]: r for r in plan["records"]}
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as c, c.begin():
        c.execute(text("SET TRANSACTION READ ONLY"))
        current_people = {str(x["id"]): x for x in rows(c, tables[PERSON])}
        baseline_ids = {str(x["id"]) for x in snapshot["tables"][PERSON]}
        report["people_before"] = len(baseline_ids)
        report["people_after"] = len(current_people)
        report["added_people"] = sorted(set(current_people) - baseline_ids)
        report["missing_people"] = sorted(baseline_ids - set(current_people))
        touched_ids = [identifier for identifier, entry in ledger["records"].items() if entry["status"] == "committed"]
        actual_states = {}
        for offset in range(0, len(touched_ids), 200):
            actual_states.update(batch_states(c, tables, touched_ids[offset:offset+200]))
        for identifier, entry in ledger["records"].items():
            if entry["status"] != "committed": continue
            actual = actual_states[identifier]
            if actual != entry["after"] or not expected_state(records[identifier], actual): report["mismatches"].append(identifier)
            else: report["verified"] += 1
        # 未执行的记录也与全表快照核对，区分同期其他编辑，不伪称零变化。
        report["other_person_changes"] = [str(p["id"]) for p in snapshot["tables"][PERSON] if str(p["id"]) not in ledger["records"] and current_people.get(str(p["id"])) != p]
        report["other_relation_changes"] = {}
        touched = {identifier for identifier, entry in ledger["records"].items() if entry["status"] == "committed"}
        for name in TABLES:
            if name in (PERSON, "interpretation_language", "interpretation_language_alias"): continue
            before = sorted([r for r in snapshot["tables"][name] if str(r["person_id"]) not in touched], key=lambda r: str(r.get("id", r.get("person_id"))))
            after = [r for r in rows(c, tables[name]) if str(r["person_id"]) not in touched]
            if before != after: report["other_relation_changes"][name] = True
    report["passed"] = not any(report[k] for k in ("mismatches", "missing_people", "added_people", "other_person_changes", "other_relation_changes")) and not any(k != "committed" and v for k, v in report["ledger_status"].items())
    atomic_json(directory / "verification.json", report)
    print(canonical({k: len(v) if isinstance(v, list) else v for k, v in report.items()}))
    return report


def rollback(engine, tables, directory, plan, identifiers=None):
    from sqlalchemy import delete, update, text
    path = directory / "ledger.json"
    ledger = read(path)
    by_id = {r["id"]: r for r in plan["records"]}
    if identifiers and not set(identifiers) <= set(ledger["records"]): raise ValueError("指定回滚人员不在该批账本中")
    for identifier, entry in ledger["records"].items():
        if identifiers and identifier not in identifiers: continue
        if entry["status"] not in {"committed", "prepared", "rollback_prepared"}: continue
        with engine.connect() as c, c.begin():
            if engine.dialect.name == "postgresql":
                c.execute(text("SELECT pg_advisory_xact_lock(260930, 1)"))
            actual = state(c, tables, identifier, lock=True)
            if entry["status"] == "rollback_prepared" and actual == entry["before"]:
                entry["status"] = "rolled_back"; atomic_json(path, ledger); continue
            if actual != entry["after"]:
                entry["rollback_status"] = "blocked_later_edit"; atomic_json(path, ledger); continue
            record = by_id[identifier]
            for item in record["adds"]:
                table = tables[item["table"]]
                c.execute(delete(table).where(table.c.id == typed(table.c.id, item["values"]["id"])))
            for item in record["updates"]:
                table = tables[item["table"]]
                old = next(x for x in entry["before"]["relations"][item["table"]] if str(x["id"]) == item["id"])
                c.execute(update(table).where(table.c.id == typed(table.c.id, item["id"])).values(**values(table, {k: old[k] for k in item["changes"]})))
            if record["changes"]:
                table = tables[PERSON]
                restore = {k: entry["before"]["person"][k] for k in [*record["changes"], "updated_at"]}
                c.execute(update(table).where(table.c.id == typed(table.c.id, identifier)).values(**values(table, restore)))
            if state(c, tables, identifier) != entry["before"]: raise ValueError("回滚核验失败")
            entry["status"] = "rollback_prepared"; atomic_json(path, ledger)
        entry["status"] = "rolled_back"; atomic_json(path, ledger)
    print(canonical(dict(Counter(x["status"] for x in ledger["records"].values()))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["snapshot", "preview", "apply", "verify", "rollback"], nargs="?", default="preview")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--expected-host", default="43.132.156.72")
    parser.add_argument("--expected-database", default="xinshi_system")
    parser.add_argument("--sha256")
    parser.add_argument("--confirm-production-write", action="store_true")
    parser.add_argument("--ids", nargs="+", help="仅用于回滚，指定本批次人才 ID")
    args = parser.parse_args()
    directory = outside(args.directory)
    if args.ids and args.mode != "rollback": raise ValueError("--ids 仅允许在回滚模式使用")
    if args.mode == "preview": build_plan(directory); return
    engine, tables = context(args)
    if args.mode == "snapshot": make_snapshot(engine, tables, directory); return
    plan = load_plan(directory, args.sha256)
    if plan["database"] != {"host": engine.url.host, "name": engine.url.database}: raise ValueError("计划目标不符")
    if args.mode in {"apply", "rollback"} and not args.confirm_production_write:
        raise ValueError("生产写入需明确授权开关")
    if args.mode == "apply": apply_plan(engine, tables, directory, plan)
    elif args.mode == "rollback": rollback(engine, tables, directory, plan, args.ids)
    elif not verify(engine, tables, directory, plan)["passed"]: raise SystemExit(2)


if __name__ == "__main__":
    main()
