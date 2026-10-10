"""读取当前 Agent 的离线初筛建议；建议不改变人工核重结论或人才档案。"""
from functools import lru_cache
import json
from pathlib import Path

from talent_duplicate_service import comparison_fingerprint

REVIEW_PATH = Path(__file__).resolve().parent / "outputs/talent-agent-review/latest.json"
BUCKETS = {"high_same", "likely_same", "different", "uncertain", "unreviewed"}


@lru_cache(maxsize=2)
def _read(path, modified, size):
    if size > 8_000_000:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("format_version") != 1:
            return {}
        groups = {}
        for item in data.get("groups", []):
            valid = isinstance(item.get("fingerprints"), dict) and isinstance(item.get("pairs"), list)
            if not valid:
                continue
            pairs = []
            for pair in item["pairs"]:
                if (pair.get("classification") not in {"same", "different", "uncertain"}
                        or pair.get("confidence") not in {"high", "medium", "low"}
                        or len(pair.get("person_ids", [])) != 2
                        or not all(identifier in item["fingerprints"] for identifier in pair["person_ids"])):
                    continue
                pairs.append({"person_ids": pair["person_ids"], "classification": pair["classification"],
                              "confidence": pair["confidence"], "reason": str(pair.get("reason", ""))[:1000],
                              "cautions": [str(value)[:300] for value in pair.get("cautions", [])[:8]]})
            groups[item["key"]] = {"fingerprints": item["fingerprints"], "pairs": pairs}
        return {"groups": groups, "created_at": data.get("created_at"), "reviewer": str(data.get("reviewer", "当前 Agent"))[:100]}
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


def group_review(report, key, members, current_fingerprints=None, conclusions=None):
    item = report.get("groups", {}).get(key)
    if not item or not item["pairs"]:
        return {"state": "unreviewed", "pairs": [], "buckets": ["unreviewed"]}
    fingerprints = current_fingerprints or {str(person.id): comparison_fingerprint(person) for person in members}
    if fingerprints != item["fingerprints"]:
        return {"state": "stale", "pairs": [], "buckets": ["unreviewed"]}
    pairs = [dict(pair, bucket=pair_bucket(pair)) for pair in item["pairs"]
             if tuple(sorted(pair["person_ids"])) not in (conclusions or {})]
    return {"state": "reviewed", "pairs": pairs, "buckets": sorted({pair["bucket"] for pair in pairs}),
            "created_at": report.get("created_at"), "reviewer": report.get("reviewer")}
