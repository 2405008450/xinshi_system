"""按已提交账本顺序重放预期快照，再对整个人才库做最终只读核验。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.normalize_talent_remarks import (TABLES, PERSON, context, outside, read, rows,
    atomic_json, load_plan, file_hash)
from tools.talent_remark_rules import canonical


def states_from_tables(data):
    relations = [n for n in TABLES if n not in (PERSON, "interpretation_language", "interpretation_language_alias")]
    result = {str(p["id"]): {"person": p, "relations": {n: [] for n in relations}} for p in data[PERSON]}
    for name in relations:
        for row in data[name]:
            result[str(row["person_id"])]["relations"][name].append(row)
        for value in result.values():
            value["relations"][name].sort(key=lambda r: str(r.get("id", r.get("person_id"))))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directories", nargs="+", type=Path, required=True)
    parser.add_argument("--expected-host", default="43.132.156.72")
    parser.add_argument("--expected-database", default="xinshi_system")
    args = parser.parse_args()
    directories = [outside(p) for p in args.directories]
    baseline = read(directories[0] / "snapshot.json")
    expected = states_from_tables(baseline["tables"])
    touched, basic, redacted = set(), set(), set()
    scalar, added, updated, status_counts = Counter(), Counter(), Counter(), Counter()
    stages = []
    rolled_back = 0
    review = []
    for directory in directories:
        plan = load_plan(directory, file_hash(directory / "plan.json"))
        ledger = read(directory / "ledger.json")
        if ledger["plan_sha256"] != file_hash(directory / "plan.json"): raise ValueError("账本与审核计划不一致")
        records = {r["id"]: r for r in plan["records"]}
        committed = 0
        for identifier, entry in ledger["records"].items():
            if entry["status"] == "rolled_back":
                if expected[identifier] != entry["before"]: raise ValueError("回滚记录与初始快照不一致")
                rolled_back += 1
                continue
            if entry["status"] != "committed": raise ValueError("仍有未成功提交的执行条目")
            if expected[identifier] != entry["before"]: raise ValueError("多批次快照衔接不一致")
            expected[identifier] = entry["after"]
            touched.add(identifier); committed += 1
            record = records[identifier]
            scalar.update(k for k in record["changes"] if k != "remarks")
            if any(k != "remarks" for k in record["changes"]) or record["adds"] or record["updates"]: basic.add(identifier)
            if "remarks" in record["changes"]: redacted.add(identifier)
            added.update(a["table"] for a in record["adds"])
            updated.update(a["table"]+"."+k for a in record["updates"] for k in a["changes"])
        stages.append({"directory": str(directory), "committed_people": committed, "plan_sha256": ledger["plan_sha256"]})
        # 最后一轮计划覆盖全部人才，以其决策作为当前待核清单。
        review = [{"id": r["id"], "resource_code": r["resource_code"], "items": [d for d in r["decisions"] if d["status"] in {"pending", "unmapped"}]} for r in plan["records"]]
        review = [r for r in review if r["items"]]
        status_counts = Counter(d["status"] for r in plan["records"] for d in r["decisions"])
    engine, tables = context(args)
    from sqlalchemy import text
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as c, c.begin():
        c.execute(text("SET TRANSACTION READ ONLY"))
        final = {name: rows(c, table) for name, table in tables.items()}
        overview_payload = c.execute(text("SELECT payload FROM talent_overview_snapshot WHERE id=1")).scalar_one_or_none()
    current = states_from_tables(final)
    mismatches = sorted(i for i in expected if current.get(i) != expected[i])
    added_people = sorted(set(current)-set(expected))
    deleted_people = sorted(set(expected)-set(current))
    catalog_changes, derived_bindings = [], []
    for name in ("interpretation_language", "interpretation_language_alias"):
        before_rows = {str(r["id"]): r for r in baseline["tables"][name]}
        after_rows = {str(r["id"]): r for r in final[name]}
        if set(before_rows) != set(after_rows): catalog_changes.append(name+".identity"); continue
        for identifier, before_row in before_rows.items():
            after_row = after_rows[identifier]
            fields = {k for k in before_row if before_row[k] != after_row[k]}
            if not fields: continue
            # 运行中的概览统计会给已登记语言补稳定绑定。只接受空键补齐，且按名称重新解析验证；
            # 不允许任何名称、ID、别名、启用状态等语种语义变化被忽略。
            if name == "interpretation_language" and fields == {"talent_overview_key"} and before_row["talent_overview_key"] is None and overview_payload:
                from talent_overview_service import resolve_overview_for_language
                aliases = [SimpleNamespace(**a) for a in final["interpretation_language_alias"] if str(a["language_id"]) == identifier]
                language = SimpleNamespace(**{**after_row, "talent_overview_key": None, "aliases": aliases})
                resolved, match_type = resolve_overview_for_language(language, data=overview_payload)
                if resolved and resolved["overview_key"] == after_row["talent_overview_key"] and match_type != "ambiguous":
                    derived_bindings.append(identifier)
                    continue
            catalog_changes.append(name+":"+",".join(sorted(fields)))
    summary = {"passed": not (mismatches or added_people or deleted_people or catalog_changes), "people_before": len(expected), "people_after": len(current), "changed_people": len(touched), "structured_people": len(basic), "remarks_redacted_people": len(redacted), "scalar_fields": dict(scalar), "added_relations": dict(added), "updated_relation_fields": dict(updated), "mismatches": len(mismatches), "added_people": len(added_people), "deleted_people": len(deleted_people), "catalog_changes": catalog_changes, "review_people": len(review), "latest_plan_decisions": dict(status_counts), "stages": stages, "rolled_back_placeholder_people": rolled_back, "external_ai_used": False}
    output = directories[-1]
    summary["validated_overview_binding_updates"] = len(derived_bindings)
    # 最终当前数据再预览；不覆盖任何已执行计划，也不制造新写入。
    from tools.normalize_talent_remarks import build_plan
    review_directory = output / "final-review"
    review_directory.mkdir(exist_ok=True)
    atomic_json(review_directory / "snapshot.json", {"tables": final, "database": baseline["database"], "git_commit": baseline["git_commit"], "limits": baseline["limits"]})
    build_plan(review_directory)
    final_plan = read(review_directory / "plan.json")
    summary["remaining_automatic_people"] = final_plan["summary"]["decisions"].get("people_with_changes", 0)
    summary["final_preview_validation_errors"] = final_plan["summary"]["validation_errors"]
    summary["passed"] = summary["passed"] and not summary["remaining_automatic_people"] and not summary["final_preview_validation_errors"]
    summary["latest_plan_decisions"] = final_plan["summary"]["decisions"]
    final_review = [{"id": r["id"], "resource_code": r["resource_code"], "items": [d for d in r["decisions"] if d["status"] in {"pending", "unmapped"}]} for r in final_plan["records"]]
    final_review = [r for r in final_review if r["items"]]
    summary["review_people"] = len(final_review)
    atomic_json(output / "review-items.json", final_review)
    atomic_json(output / "final-summary.json", summary)
    atomic_json(output / "final-audit.json", {"summary": summary, "mismatched_ids": mismatches, "added_ids": added_people, "deleted_ids": deleted_people})
    print(canonical(summary))
    if not summary["passed"]: raise SystemExit(2)


if __name__ == "__main__": main()
