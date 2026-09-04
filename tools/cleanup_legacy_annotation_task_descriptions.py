"""清理旧标注项目导入时写入“具体任务”的过程性文本标记。"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import annotation_ops_service  # noqa: F401  注册 SQLAlchemy 关联模型
import annotation_service  # noqa: F401  注册 SQLAlchemy 关联模型
from annotation_models import AnnotationProject
from database import SessionLocal


REMOVED_LINES = {
    "【待人工处理（原表预留）】",
}
LABEL_REPLACEMENTS = {
    "原项目类型：": "项目类型：",
    "咨询时间（未识别）：": "咨询时间：",
    "开始合作时间（未识别）：": "开始合作时间：",
    "客户部（未匹配唯一用户）：": "客户部：",
    "项目部（未匹配唯一项目经理用户）：": "项目部：",
    "客户名称（系统无精确匹配，将创建待完善客户）：": "客户名称：",
    "原项目路径（未通过路径规则）：": "项目路径：",
}

PROCESS_MARKERS = (
    "旧台账来源行：",
    "【待人工处理（原表预留）】",
    "（已同时整理为价格明细）",
)


def clean_description(value: str | None) -> str | None:
    if not value:
        return None
    result: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if re.fullmatch(r"旧台账来源行：\d+", line) or line in REMOVED_LINES:
            continue
        line = line.replace("（已同时整理为价格明细）", "")
        for source, target in LABEL_REPLACEMENTS.items():
            if line.startswith(source):
                line = target + line[len(source):]
                break
        if not line:
            if result and result[-1] != "":
                result.append("")
            continue
        result.append(line)
    while result and not result[-1]:
        result.pop()
    return "\n".join(result) or None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-host", default="WIN-LOLJ8UHT2G5")
    args = parser.parse_args()
    if args.apply and socket.gethostname().casefold() != args.expected_host.casefold():
        raise RuntimeError(f"主机校验失败：当前为 {socket.gethostname()}，预期为 {args.expected_host}")

    db = SessionLocal()
    report = {"mode": "apply" if args.apply else "dry-run", "changed": [], "unchanged": [], "failed": []}
    try:
        projects = db.query(AnnotationProject).filter(
            AnnotationProject.idempotency_key.like("legacy-annotation-%")
        ).order_by(AnnotationProject.order_no).all()
        for project in projects:
            before = project.task_description
            after = clean_description(before)
            if before == after:
                report["unchanged"].append({"id": str(project.id), "order_no": project.order_no})
                continue
            item = {
                "id": str(project.id),
                "order_no": project.order_no,
                "before": before,
                "after": after,
            }
            if args.apply:
                try:
                    project.task_description = after
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    report["failed"].append({**item, "error": str(exc)})
                    continue
            report["changed"].append(item)
    finally:
        db.close()

    report["summary"] = {key: len(report[key]) for key in ("changed", "unchanged", "failed")}
    report["marker_counts"] = {
        marker: sum(marker in (project.task_description or "") for project in projects)
        for marker in PROCESS_MARKERS
    }
    report["nonempty_task_descriptions"] = sum(bool(project.task_description) for project in projects)
    report_path = Path(args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
