"""导入审核后的陈佳名单。默认只读校验，--apply 才写入；同名独立保留。"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from resource_schemas import ResourcePersonCreate, ResourcePersonDetailResponse

SOURCE = "陈佳译员名单"


def normalize(value):
    return "".join(str(value or "").split()).casefold()


def validate(plan):
    if plan.get("version") != "chen-talents-v1" or plan.get("source") != SOURCE:
        raise ValueError("不是审核的陈佳名单计划")
    keys = set()
    result = []
    for record in plan["records"]:
        expected = f"chen20260923:{plan['source_sha256']}:{record['row']}"
        if record["idempotency_key"] != expected or expected in keys:
            raise ValueError("行号或幂等键异常")
        keys.add(expected)
        payload = ResourcePersonCreate.model_validate(record["payload"])
        if (payload.registration_source != SOURCE or payload.overall_score is not None
                or payload.annotation_language_skills or payload.capabilities or payload.certificates):
            raise ValueError("导入计划不符合已确认的字段规则")
        result.append(payload)
    if len(result) != 51:
        raise ValueError("审核清单应有51条")
    return result


def compare(person, payload):
    actual = ResourcePersonDetailResponse.model_validate(person).model_dump(mode="json")
    expected = payload.model_dump(mode="json", exclude={"allow_duplicate"})
    for field, value in expected.items():
        # 新档案编号由数据库生成；原表未提供编号时保留生成结果。
        if field == "resource_code" and value is None:
            if not actual.get(field):
                raise ValueError("数据库未生成人才编号")
            continue
        if field == "language_skills":
            observed = sorted(actual[field], key=lambda item: item["sort_order"])
            wanted = sorted(value, key=lambda item: item["sort_order"])
            if len(observed) != len(wanted):
                raise ValueError("导入后语言数量不符")
            for a, b in zip(observed, wanted):
                if any(a.get(k) != v for k, v in b.items() if k != "id"):
                    raise ValueError("导入后语言内容不符")
        elif actual.get(field) != value:
            raise ValueError(f"导入后字段不符：{field}")


def apply(plan, payloads, output):
    from database import engine, SessionLocal
    if engine.url.host != "43.132.156.72" or engine.url.database != "xinshi_system":
        raise RuntimeError("目标不是本次授权的数据库")
    import main as _models  # 注册跨模块 ORM 关系，不启动服务。
    from sqlalchemy import text
    from resource_models import ResourcePerson, ResourceLanguageSkill
    from resource_service import _person_options, count_talents

    output.mkdir(parents=True, exist_ok=False)
    report = {"source": SOURCE, "created": [], "skipped": [], "verified": 0}
    with SessionLocal() as db, db.begin():
        db.execute(text("SELECT pg_advisory_xact_lock(2609, 51)"))
        before = [dict(row) for row in db.execute(text('SELECT * FROM resource_person')).mappings()]
        (output / "before.json").write_text(json.dumps(before, ensure_ascii=False, default=str), encoding="utf-8")
        people = db.query(ResourcePerson).all()
        by_key = {person.idempotency_key: person for person in people if person.idempotency_key}
        aliases, contacts = set(), set()
        for person in people:
            aliases.update(normalize(value) for value in [person.full_name, person.chinese_name, person.english_name,
                           person.nickname, *(person.other_names or [])] if value)
            if person.wechat:
                contacts.add(normalize(person.wechat))
        names = Counter(normalize(p.full_name) for r, p in zip(plan["records"], payloads) if r["idempotency_key"] not in by_key)
        imported = []
        for record, payload in zip(plan["records"], payloads):
            prior = by_key.get(record["idempotency_key"])
            if prior:
                if prior.registration_source != SOURCE:
                    raise ValueError("幂等键来源冲突")
                report["skipped"].append({"row": record["row"], "id": str(prior.id)})
                imported.append((prior.id, payload))
                continue
            data = payload.model_dump(exclude={"allow_duplicate", "capabilities", "written_profile", "interpretation_profile",
                "annotation_profile", "annotation_language_skills", "career_profile", "education_experiences", "language_skills", "certificates"})
            review = bool(record["duplicate_review_required"] or normalize(payload.full_name) in aliases
                          or names[normalize(payload.full_name)] > 1
                          or (payload.wechat and normalize(payload.wechat) in contacts))
            person = ResourcePerson(**data, idempotency_key=record["idempotency_key"], duplicate_review_required=review)
            person.language_skills = [ResourceLanguageSkill(**skill.model_dump(exclude={"id"})) for skill in payload.language_skills]
            db.add(person)
            db.flush()
            compare(person, payload)
            imported.append((person.id, payload))
            report["created"].append({"row": record["row"], "id": str(person.id), "duplicate_review_required": review})
    # 提交后另开会话核验，避免仅验证未提交的 ORM 对象。
    with SessionLocal() as db:
        loaded = {p.id: p for p in db.query(ResourcePerson).options(*_person_options()).filter(ResourcePerson.id.in_([i for i, _ in imported])).all()}
        for identifier, payload in imported:
            compare(loaded[identifier], payload)
        report["verified"] = len(loaded)
        report["placeholder_names"] = sum(p.full_name.startswith("待确认姓名") for p in loaded.values())
        report["annotation_languages"] = sum(len(p.annotation_language_skills) for p in loaded.values())
        report["overall_scores_filled"] = sum(p.overall_score is not None for p in loaded.values())
        report["duplicate_review_records"] = sum(p.duplicate_review_required for p in loaded.values())
        report["source_filter_count"] = count_talents(db, field_filters={"registration_source": {"op": "eq", "value": SOURCE}})
        current = {str(row["id"]): dict(row) for row in db.execute(text('SELECT * FROM resource_person')).mappings()}
        changes = [{field for field, value in row.items() if current[str(row['id'])].get(field) != value} for row in before]
        report["existing_records_changed"] = sum(bool(fields) for fields in changes)
        # 同名检测触发器会同步刷新旧档案的系统标记，独立于业务资料变更统计。
        report["existing_duplicate_flags_refreshed"] = sum(fields == {"name_duplicate"} for fields in changes)
        report["existing_business_records_changed"] = sum(bool(fields - {"name_duplicate"}) for fields in changes)
    (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: len(v) if isinstance(v, list) else v for k, v in report.items()}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    content = args.plan.read_bytes()
    if hashlib.sha256(content).hexdigest() != args.sha256:
        raise ValueError("计划文件与已审核版本不一致")
    plan = json.loads(content)
    payloads = validate(plan)
    print(json.dumps({"validated": len(payloads), "apply": args.apply}))
    if args.apply:
        if not args.output or args.output.resolve().is_relative_to(ROOT):
            raise ValueError("必须指定仓库外的新输出目录")
        apply(plan, payloads, args.output)
