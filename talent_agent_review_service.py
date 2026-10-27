"""读取当前 Agent 的离线建议；逐对校验，绝不自动确认身份或写入人才档案。"""
from functools import lru_cache
import itertools
import json
from pathlib import Path

from talent_duplicate_service import comparison_fingerprint, digest

REVIEW_PATH = Path(__file__).resolve().parent / "outputs/talent-agent-review/latest.json"
BUCKETS = {"high_same", "likely_same", "different", "uncertain", "unreviewed"}


def pair_key(ids):
    return tuple(sorted(str(value) for value in ids))


@lru_cache(maxsize=2)
def _read(path, modified, size):
    if size > 32_000_000:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        version = data.get("format_version")
        if version not in {1, 2}:
            return {}
        groups = {}
        for item in data.get("groups", []):
            if not isinstance(item.get("fingerprints"), dict) or not isinstance(item.get("pairs"), list):
                continue
            pairs, seen, duplicate = {}, set(), set()
            for pair in item["pairs"]:
                if pair.get("reviewed") is False:
                    continue
                ids = pair.get("person_ids", [])
                if (pair.get("classification") not in {"same", "different", "uncertain"}
                        or not str(pair.get("reason", "")).strip()
                        or pair.get("confidence") not in {"high", "medium", "low"}
                        or not isinstance(ids, list) or len(ids) != 2 or len(set(ids)) != 2
                        or not all(identifier in item["fingerprints"] for identifier in ids)):
                    continue
                key = pair_key(ids)
                if key in seen:
                    duplicate.add(key)
                seen.add(key)
                pairs[key] = {"person_ids": ids, "classification": pair["classification"],
                              "confidence": pair["confidence"], "reason": str(pair.get("reason", ""))[:1000],
                              "cautions": [str(value)[:300] for value in pair.get("cautions", [])[:8]],
                              "evidence_version": pair.get("evidence_version")}
            # 重复判断不能任取一次，避免最后一次覆盖矛盾结论。
            groups[item["key"]] = {"fingerprints": item["fingerprints"],
                                   "pairs": [value for key, value in pairs.items() if key not in duplicate]}
        return {"format_version": version, "report_id": digest(data), "groups": groups,
                "group_count": data.get("group_count", len(groups)), "pair_count": data.get("pair_count"),
                "reviewed_pair_count": data.get("reviewed_pair_count"), "source_complete": data.get("source_complete", True),
                "created_at": data.get("created_at"), "reviewer": str(data.get("reviewer", "当前 Agent"))[:100]}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {}


def load_report():
    try:
        stat = REVIEW_PATH.stat()
        return _read(str(REVIEW_PATH), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return {}


def pair_bucket(pair):
    if pair["classification"] == "same":
        return "high_same" if pair["confidence"] == "high" else "likely_same"
    return pair["classification"]


def group_review(report, key, members, current_fingerprints=None, conclusions=None, evidence=None):
    item = report.get("groups", {}).get(key)
    fingerprints = current_fingerprints or {str(person.id): comparison_fingerprint(person) for person in members}
    conclusions = conclusions or {}
    outstanding = {pair for pair in itertools.combinations(sorted(fingerprints), 2) if conclusions.get(pair) != "different"}
    result = {"state": "unreviewed", "pairs": [], "buckets": ["unreviewed"],
              "report_id": report.get("report_id"), "created_at": report.get("created_at"),
              "reviewer": report.get("reviewer"), "unreviewed_pair_count": len(outstanding), "stale_pair_count": 0}
    if not item or not item["pairs"]:
        return result
    version = report.get("format_version", 1)
    # 旧报告没有逐对证据版本，维持原来的整组失效语义。
    if version == 1 and fingerprints != item["fingerprints"]:
        return dict(result, state="stale", stale_pair_count=len(outstanding))
    current_evidence = {pair_key(pair["person_ids"]): pair for pair in (evidence or [])}
    pairs, stale = [], 0
    for pair in item["pairs"]:
        ids = pair_key(pair["person_ids"])
        if ids not in outstanding:
            continue
        valid = all(item["fingerprints"].get(identifier) == fingerprints.get(identifier) for identifier in ids)
        if version == 2:
            valid = valid and bool(pair.get("evidence_version")) and pair["evidence_version"] == current_evidence.get(ids, {}).get("evidence_version")
        if not valid:
            stale += 1
            continue
        pairs.append(dict(pair, bucket=pair_bucket(pair)))
    remaining = len(outstanding) - len(pairs)
    buckets = {pair["bucket"] for pair in pairs}
    if remaining:
        buckets.add("unreviewed")
    return dict(result, pairs=pairs, buckets=sorted(buckets), stale_pair_count=stale,
                unreviewed_pair_count=remaining,
                state="partial" if pairs and remaining else "reviewed" if pairs or not outstanding else "stale" if stale else "unreviewed")


def identity_subgroups(member_ids, evidence, review, conclusions=None):
    """只推荐完整且互不重叠的高置信分量；链式及重叠关系全部留待决。"""
    ids = sorted(str(value) for value in member_ids)
    conclusions = conclusions or {}
    facts = {pair_key(pair["person_ids"]): pair for pair in evidence}
    suggestions = {pair_key(pair["person_ids"]): pair for pair in review.get("pairs", [])}
    graph = {identifier: set() for identifier in ids}
    for key, pair in suggestions.items():
        if (pair["classification"] == "same" and pair["confidence"] == "high"
                and not facts.get(key, {}).get("identity_conflicts") and not conclusions.get(key)):
            a, b = key
            graph[a].add(b)
            graph[b].add(a)
    subgroups, ambiguous, visited = [], [], set()
    for root in ids:
        if root in visited or not graph[root]:
            continue
        stack, component = [root], set()
        while stack:
            node = stack.pop()
            if node not in component:
                component.add(node)
                stack.extend(graph[node] - component)
        visited.update(component)
        pairs = list(itertools.combinations(sorted(component), 2))
        if all(b in graph[a] for a, b in pairs):
            subgroups.append({"id": digest(sorted(component)), "person_ids": sorted(component),
                              "basis": [suggestions[pair] for pair in pairs], "report_id": review.get("report_id")})
        else:
            ambiguous.extend([list(pair) for pair in pairs if pair in suggestions and pair[1] in graph[pair[0]]])
    assigned = {identifier for group in subgroups for identifier in group["person_ids"]}
    pending = [list(pair) for pair in itertools.combinations(ids, 2) if conclusions.get(pair) != "different"]
    return {"subgroups": subgroups, "standalone_ids": [identifier for identifier in ids if identifier not in assigned],
            "ambiguous_pairs": ambiguous, "unresolved_pairs": pending,
            "counts": {"recommended_subgroups": len(subgroups), "standalone_records": len(ids) - len(assigned),
                       "unresolved_pairs": len(pending)}}
