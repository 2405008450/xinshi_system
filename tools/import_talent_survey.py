"""校验并导入已审核的人才问卷计划；默认仅校验，显式 --apply 才写入。

正式库还必须传入 --confirm-production-write，并由操作者事先获得用户授权。
不自动迁移、不覆盖已有档案。新增语言及人才统一在单个事务中提交。
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from uuid import UUID

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from resource_schemas import ResourcePersonCreate  # noqa: E402
from tools.prepare_talent_survey import SOURCE, key  # noqa: E402


def validate_plan(plan):
    if plan.get("version") != 1 or plan.get("source") != SOURCE:
        raise ValueError("未知导入计划版本或来源")
    rows, keys = set(), set()
    payloads = []
    for record in plan["records"]:
        row = record["row"]
        expected_key = f"survey2609:{plan['source_sha256']}:{row}"
        if record["idempotency_key"] != expected_key or row in rows or expected_key in keys:
            raise ValueError("导入行号或幂等键异常")
        rows.add(row)
        keys.add(expected_key)
        payload = ResourcePersonCreate.model_validate(record["payload"])
        if payload.registration_source != SOURCE or payload.annotation_language_skills or payload.capabilities:
            raise ValueError(f"第 {row} 行违反来源、专业能力或标注语言留空约定")
        if payload.birth_date or payload.birth_year_month:
            raise ValueError("原表只有年龄，不允许自动推算出生年月")
        if any(item.material_received for item in payload.certificates):
            raise ValueError("不能将问卷自报证书标记为已收到材料")
        payloads.append(payload)
    if len(payloads) != plan["summary"]["records"]:
        raise ValueError("计划记录数不一致")
    return payloads


def apply_plan(plan, payloads, args):
    from database import engine
    if engine.url.host != args.expected_database_host:
        raise RuntimeError("数据库主机与指定目标不一致，停止写入")
    if engine.url.host == "43.132.156.72" and not args.confirm_production_write:
        raise RuntimeError("这是正式数据库；必须先获得用户确认，再显式授权正式库写入")
    if not args.backup or not args.report:
        raise ValueError("写入前必须指定仓库外 --backup 和 --report 路径")
    for path in (args.backup, args.report):
        if path.resolve().is_relative_to(PROJECT_ROOT) or path.exists():
            raise ValueError("备份和结果必须是仓库外的全新文件，禁止覆盖")
        path.parent.mkdir(parents=True, exist_ok=True)
    import main as _registered_models  # noqa: F401
    from database import SessionLocal
    from sqlalchemy import inspect, text
    from interpretation_models import InterpretationLanguage
    from resource_models import ResourcePerson, ResourceLanguageSkill, ResourceCertificate, ResourceEducationExperience
    from resource_schemas import ResourcePersonDetailResponse

    if "registration_source" not in {c["name"] for c in inspect(engine).get_columns("resource_person")}:
        raise RuntimeError("请先审核并执行来源字段迁移")
    report = {"source": SOURCE, "source_sha256": plan["source_sha256"], "created": [], "skipped": [], "new_languages": []}
    with SessionLocal() as db, db.begin():
        # 同一批导入串行化，避免重复执行导致并发重复档案。
        db.execute(text("SELECT pg_advisory_xact_lock(2609, 765)"))
        tables = ["resource_person", "resource_language_skill", "resource_certificate", "resource_education_experience",
                  "interpretation_language", "interpretation_language_alias"]
        snapshot = {name: [dict(row) for row in db.execute(text(f'SELECT * FROM "{name}"')).mappings()] for name in tables}
        args.backup.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        language_ids = {str(row.id): row for row in db.query(InterpretationLanguage).all()}
        label_ids = {row.label: str(row.id) for row in language_ids.values()}
        remap = {}
        for item in plan["new_languages"]:
            identifier, label = item["id"], item["label"]
            if label in label_ids:
                remap[identifier] = label_ids[label]
                continue
            if identifier in language_ids:
                raise ValueError("新增语种 ID 冲突")
            language = InterpretationLanguage(id=UUID(identifier), label=label)
            db.add(language)
            language_ids[identifier] = language
            label_ids[label] = identifier
            report["new_languages"].append(item)
        db.flush()
        existing = db.query(ResourcePerson).all()
        existing_keys = {person.idempotency_key: person for person in existing if person.idempotency_key}
        name_counts = Counter(key(person.full_name) for person in existing)
        wechat_counts = Counter(key(person.wechat or "") for person in existing)
        name_counts.update(key(p.full_name) for r, p in zip(plan["records"], payloads) if r["idempotency_key"] not in existing_keys)
        wechat_counts.update(key(p.wechat or "") for r, p in zip(plan["records"], payloads) if r["idempotency_key"] not in existing_keys)
        for record, payload in zip(plan["records"], payloads):
            idempotency_key = record["idempotency_key"]
            if idempotency_key in existing_keys:
                prior = existing_keys[idempotency_key]
                if prior.registration_source != SOURCE:
                    raise ValueError("幂等键被其他来源使用，停止写入")
                report["skipped"].append({"row": record["row"], "id": str(prior.id)})
                continue
            data = payload.model_dump(exclude={"allow_duplicate", "capabilities", "written_profile", "interpretation_profile",
                "annotation_profile", "annotation_language_skills", "career_profile", "education_experiences", "language_skills", "certificates"})
            review = name_counts[key(payload.full_name)] > 1 or bool(payload.wechat and wechat_counts[key(payload.wechat)] > 1)
            person = ResourcePerson(**data, idempotency_key=idempotency_key, duplicate_review_required=review)
            for collection, model in [("language_skills", ResourceLanguageSkill), ("certificates", ResourceCertificate),
                                      ("education_experiences", ResourceEducationExperience)]:
                for child in getattr(payload, collection):
                    child_data = child.model_dump(exclude={"id"})
                    if child_data.get("language_id"):
                        identifier = remap.get(str(child_data["language_id"]), str(child_data["language_id"]))
                        if identifier not in language_ids:
                            raise ValueError(f"第 {record['row']} 行语种已不存在")
                        child_data["language_id"] = UUID(identifier)
                    getattr(person, collection).append(model(**child_data))
            db.add(person)
            db.flush()
            # 验证导入后的记录确实可由详情接口完整序列化。
            ResourcePersonDetailResponse.model_validate(person)
            if person.annotation_language_skills:
                raise ValueError("标注语言必须留空")
            report["created"].append({"row": record["row"], "id": str(person.id), "duplicate_review_required": review})
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"created": len(report["created"]), "skipped": len(report["skipped"]), "new_languages": len(report["new_languages"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--plan-sha256", help="审核通过的计划文件 SHA-256；写入时必填")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-database-host")
    parser.add_argument("--confirm-production-write", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    content = args.plan.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if args.apply and (not args.plan_sha256 or args.plan_sha256 != digest or not args.expected_database_host):
        raise ValueError("写入必须提供审核计划的 SHA-256 和目标数据库主机")
    plan = json.loads(content)
    payloads = validate_plan(plan)
    print(json.dumps({"validated": len(payloads), "plan_sha256": digest}, ensure_ascii=False))
    if args.apply:
        print(json.dumps(apply_plan(plan, payloads, args), ensure_ascii=False))


if __name__ == "__main__":
    main()
