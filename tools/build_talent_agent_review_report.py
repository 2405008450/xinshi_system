"""将当前 Agent 的离线判断整理为工作台可读报告；不自行判定同一人。"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from business_time import business_iso, business_now


def build(source, decisions, destination):
    data = json.loads(source.read_text(encoding="utf-8"))
    judgments = json.loads(decisions.read_text(encoding="utf-8"))
    overrides = {}
    for judgment in judgments["pairs"]:
        index = tuple(judgment.pop("index"))
        if index in overrides or judgment["classification"] not in {"same", "different", "uncertain"} or judgment["confidence"] not in {"high", "medium", "low"}:
            raise ValueError("判断重复或格式无效")
        overrides[index] = judgment
    groups, counts, applied = [], Counter(), set()
    for group_index, group in enumerate(data["groups"]):
        pairs = []
        for pair_index, pair in enumerate(group["pairs"]):
            index = (group_index, pair_index)
            judgment = overrides.get(index, judgments["default"])
            if index in overrides:
                applied.add(index)
            pairs.append({"person_ids": pair["person_ids"], "codes": pair["codes"], **judgment})
            counts[judgment["classification"] + ":" + judgment["confidence"]] += 1
        groups.append({"key": group["key"], "fingerprints": group["fingerprints"], "pairs": pairs})
    if applied != set(overrides):
        raise ValueError("判断引用了不存在的记录对")
    report = {"format_version": 1, "reviewer": judgments["reviewer"], "created_at": business_iso(business_now()),
              "source_created_at": data["created_at"], "scope_note": judgments["scope_note"],
              "counts": dict(counts), "group_count": len(groups), "pair_count": sum(len(g["pairs"]) for g in groups), "groups": groups}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 当前 Agent 人才同名初筛报告", "", "生成时间：" + report["created_at"], "",
             report["scope_note"], "", f"覆盖 {report['group_count']} 组、{report['pair_count']} 对。", "",
             "| 分流 | 记录对数 |", "| --- | ---: |"]
    labels = {"same:high": "高置信度同一人", "same:medium": "可能同一人，需复核", "different:medium": "疑似不同人，需复核", "uncertain:low": "证据不足／资料矛盾，二次核对"}
    lines += [f"| {labels.get(key, key)} | {value} |" for key, value in sorted(counts.items())]
    lines += ["", "## 高置信度候选", "", "| 姓名组 | 档案 | 判断依据及仍需确认的信息 |", "| --- | --- | --- |"]
    for group in groups:
        for pair in group["pairs"]:
            if pair["classification"] == "same" and pair["confidence"] == "high":
                reason = "；".join(value.rstrip("。；") for value in [pair["reason"], *pair.get("cautions", [])] if value) + "。"
                lines.append(f"| {group['key']} | {' / '.join(pair['codes'])} | {reason.replace('|', '／')} |")
    lines += ["", "同一组可同时包含高置信度候选和待复核成员。本报告不进行传递式身份认定，不修改人才档案或归档关系。置信度为当前 Agent 对证据的分档判断，不是已验证的概率。工作台在资料或成员变化后使该组旧建议失效。"]
    destination.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"groups": len(groups), "pairs": report["pair_count"], "counts": dict(counts), "report": str(destination)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/talent-agent-review/latest.json")
    args = parser.parse_args()
    build(args.source, args.decisions, args.output)
