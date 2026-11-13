"""从报告压缩包提供只读结构化数据，不依赖共享盘或业务数据库。"""

import gzip
import hashlib
import json
import zlib
from functools import lru_cache
from pathlib import Path


REPORT_ID = "minority-transcription-20261113"
REPORT_PACKAGE = Path(__file__).resolve().parent / "frontend" / "reports" / f"{REPORT_ID}.json.gz"
COHORTS = ("public_dataset", "human_independent", "human_revision", "human_after_revision")


class ReportDataError(Exception):
    """报告文件缺失或格式不正确。"""


class ReportDataset:
    def __init__(self, package: bytes):
        self.revision = hashlib.sha256(package).hexdigest()
        self.files = json.loads(gzip.decompress(package))
        self.summary = json.loads(self.files["summary.json"])
        for key, expected_type in {
            "schema_version": str, "generated_date": str, "human_analysis_date": str,
            "stats": dict, "models": dict, "languages": list, "model_summary": list,
            "public_results": list, "methods": list,
        }.items():
            if not isinstance(self.summary[key], expected_type):
                raise ValueError("报告汇总格式不正确")
        self.languages = {row["language_code"]: row for row in self.summary["languages"]}
        if not self.languages or not isinstance(self.summary["models"], dict):
            raise ValueError("报告汇总格式不正确")

    def metadata(self):
        return {
            "api_version": "1.0",
            "report_id": REPORT_ID,
            "revision": self.revision,
            "schema_version": self.summary["schema_version"],
            "generated_date": self.summary["generated_date"],
            "human_analysis_date": self.summary["human_analysis_date"],
            "language_count": len(self.languages),
            "models": self.summary["models"],
            "cohorts": list(COHORTS),
            "methods": self.summary["methods"],
            "field_notes": {
                "cer": "字符差异率，越低越好，可超过 1；null 表示不可计算，不能当作 0。",
                "wer": "词差异率，越低越好；部分语种没有可靠分词，保留 null。",
                "success": "接口返回成功标记，不代表文本完整或识别准确。",
                "cohort": "不同来源与比较对象必须分开统计，不能直接平均或合并 CER。",
                "reference": "对照原文；不保证人工对照文本一定正确。",
                "hypothesis": "待比较原文；文本差异不能自动判定谁对谁错。",
                "generated_date": "原报告汇总日期，为纯日期，不附加时间或时区。",
                "start/end": "音频片段相对起止秒数，不是业务日期时间。",
            },
        }

    def details(self, language_code, *, model=None, cohort=None, success=None,
                skip=0, limit=50, include_diff_html=False):
        # 先验证目录中的语种代码，禁止将任意用户路径拼入文件名。
        if language_code not in self.languages:
            raise KeyError(language_code)
        rows = _read_details(self, language_code)
        rows = [row for row in rows if
                (model is None or row.get("model") == model)
                and (cohort is None or row.get("cohort") == cohort)
                and (success is None or row.get("success") is success)]
        excluded = set() if include_diff_html else {"reference_diff_html", "hypothesis_diff_html"}
        return {
            "report_id": REPORT_ID,
            "revision": self.revision,
            "language_code": language_code,
            "filters": {"model": model, "cohort": cohort, "success": success},
            "skip": skip,
            "limit": limit,
            "total": len(rows),
            "items": [{key: value for key, value in row.items() if key not in excluded}
                      for row in rows[skip:skip + limit]],
        }


@lru_cache(maxsize=8)
def _read_details(dataset, language_code):
    try:
        rows = json.loads(dataset.files[f"details/{language_code}.json"])
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("语种明细格式不正确")
        return rows
    except (KeyError, ValueError, TypeError) as exc:
        raise ReportDataError("报告语种明细不可用") from exc


@lru_cache(maxsize=1)
def _load_report(path: str, mtime_ns: int, size: int):
    # mtime_ns 与 size 仅用于缓存失效，不转换为业务时间。
    return ReportDataset(Path(path).read_bytes())


def get_report_dataset():
    try:
        stat = REPORT_PACKAGE.stat()
        return _load_report(str(REPORT_PACKAGE), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError, TypeError, KeyError, EOFError, zlib.error) as exc:
        raise ReportDataError("转写报告数据包不可用") from exc
