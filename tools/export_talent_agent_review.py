"""只读导出同名候选供当前 Codex 会话识别；不调用外部模型，不修改业务库。"""
import argparse
from collections import defaultdict
import itertools
import json
from pathlib import Path
import re
import socket
import sys
from types import SimpleNamespace

from sqlalchemy import func, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main  # 仅注册模型，不运行 FastAPI lifespan 或结构迁移。

from business_time import business_iso, business_now
from database import engine
from resource_models import ResourcePerson
from resource_service import _person_options
from talent_duplicate_service import (archive_options, active_query, name_key, contact_identifiers,
    comparison_fingerprint, _business_values, _pair_decisions, _decision_query, pair_evidence,
    field_state, review_ready)
from talent_privacy import RESOURCE_CONTACT_FIELDS

def export(destination):
    if socket.gethostname().upper() != "PC" or ROOT != Path(r"E:\xinshi_system"):
        raise SystemExit("只允许在 PC 的项目目录只读导出")
    destination.mkdir(parents=True, exist_ok=True)
    with engine.connect() as connection, Session(bind=connection) as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        ready = review_ready(db)
        query = active_query(db, db.query(ResourcePerson))
        normalized = func.resource_person_duplicate_name_key(ResourcePerson.full_name)
        duplicate_keys = active_query(db, db.query(normalized)).group_by(normalized).having(func.count(ResourcePerson.id) > 1)
        people = query.filter(normalized.in_(duplicate_keys)).options(*_person_options(), *archive_options(db)).all()
        grouped = defaultdict(list)
        for person in people:
            grouped[name_key(person.full_name)].append(person)
        operations = _decision_query(db).order_by("created_at").all() if ready else []
        contacts = defaultdict(set)
        columns = [getattr(ResourcePerson, field) for field in RESOURCE_CONTACT_FIELDS]
        all_contacts = active_query(db, db.query(ResourcePerson.id, ResourcePerson.full_name, *columns)).all()
        for row in all_contacts:
            identifiers = contact_identifiers(SimpleNamespace(**row._mapping))
            for kind, values in identifiers.items():
                for value in values:
                    contacts[(kind, value)].add(name_key(row.full_name))
        exported = []
        for key, members in sorted(grouped.items()):
            states = _pair_decisions(members, [op for op in operations if op.name_key == key])
            if all(tuple(sorted((str(a.id), str(b.id)))) in states for a, b in itertools.combinations(members, 2)):
                continue
            original_contacts = set()
            for person in members:
                for field in RESOURCE_CONTACT_FIELDS:
                    value = str(getattr(person, field, None) or "").strip()
                    if len(value) > 2:
                        original_contacts.add(value)
                for values in contact_identifiers(person).values():
                    original_contacts.update(value for value in values if len(value) > 2)
            sensitive = re.compile("|".join(re.escape(value) for value in sorted(original_contacts, key=len, reverse=True)), re.I) if original_contacts else None
            def scrub(value):
                if isinstance(value, dict):
                    return {k: scrub(v) for k, v in value.items() if k not in {"certificate_no", "language_id", "source_language_id", "target_language_id"}}
                if isinstance(value, list):
                    return [scrub(v) for v in value]
                if isinstance(value, str):
                    value = re.sub(r"https?://\S+", "[原附件链接]", value)
                    value = sensitive.sub("[联系方式]", value) if sensitive else value
                    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[邮箱]", value)
                    value = re.sub(r"\+?\d[\d ()-]{5,}\d", "[电话]", value)
                    return value[:1000]
                return value
            values = {str(person.id): _business_values(person) for person in members}
            pairs = []
            for a, b in itertools.combinations(members, 2):
                pair_ids = tuple(sorted((str(a.id), str(b.id))))
                if pair_ids in states:
                    continue
                left, right = values[str(a.id)], values[str(b.id)]
                evidence = pair_evidence(a, b)
                matches = {}
                shared_names = {}
                for kind, found in contact_identifiers(a).items():
                    shared = found & contact_identifiers(b)[kind]
                    if shared:
                        matches[kind] = len(shared)
                        shared_names[kind] = max(len(contacts[(kind, value)]) for value in shared)
                meaningful = {field for field in left.keys() | right.keys() if field not in {*RESOURCE_CONTACT_FIELDS,
                    "full_name", "chinese_name", "wechat_accounts", "resume_path", "status", "cooperation_type",
                    "registration_source", "capabilities", "remarks", "overall_rating", "annotation_willingness"}}
                equal = {field: scrub(left[field]) for field in meaningful if field_state([left.get(field), right.get(field)]) == "same"}
                differences = {field: [scrub(left.get(field)), scrub(right.get(field))] for field in meaningful
                               if field_state([left.get(field), right.get(field)]) == "conflict"}
                supplementary = {field: [scrub(left.get(field)), scrub(right.get(field))] for field in meaningful
                                 if field_state([left.get(field), right.get(field)]) == "complement"}
                pairs.append({"codes": [a.resource_code, b.resource_code], "person_ids": [str(a.id), str(b.id)],
                              "contact_matches": matches, "shared_contact_name_counts": shared_names,
                              "identity_conflicts": evidence["identity_conflicts"], "equal": equal,
                              "differences": differences, "supplementary": supplementary})
            exported.append({"key": key, "fingerprints": {str(p.id): comparison_fingerprint(p) for p in members},
                             "members": [{"id": str(p.id), "code": p.resource_code, "name": p.full_name,
                                          "source": scrub(p.registration_source), "remarks": scrub(p.remarks),
                                          "created_at": business_iso(p.created_at)} for p in members], "pairs": pairs})
        report = {"created_at": business_iso(business_now()), "database": {"host": engine.url.host, "port": engine.url.port, "name": engine.url.database},
                  "groups": exported, "group_count": len(exported), "pair_count": sum(len(group["pairs"]) for group in exported)}
        (destination / "input.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        brief = []
        for index, group in enumerate(exported):
            for pair_index, pair in enumerate(group["pairs"]):
                brief.append({"index": [index, pair_index], "name": group["key"], **{key: value for key, value in pair.items() if key != "person_ids"}})
        (destination / "evidence.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in brief), encoding="utf-8")
        print(json.dumps({key: report[key] for key in ("created_at", "database", "group_count", "pair_count")}, ensure_ascii=False))
        print(json.dumps({"contact_pairs": sum(bool(p["contact_matches"]) for g in exported for p in g["pairs"]),
                          "identity_conflicts": sum(bool(p["identity_conflicts"]) for g in exported for p in g["pairs"]),
                          "output": str(destination)}, ensure_ascii=False))
        db.rollback()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / f"outputs/talent-agent-review-{business_now():%Y%m%d-%H%M%S%z}")
    export(parser.parse_args().output.resolve())
