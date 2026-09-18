"""审计共享语种与人才概览的确定性映射；默认只读，--apply 才落库。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 注册主应用全部 ORM 模型，保证独立脚本中的跨模块 relationship 可解析。
import main as _application_models  # noqa: E402,F401
from database import SessionLocal  # noqa: E402
from talent_overview_service import audit_language_mappings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="审计人才概览语种映射")
    parser.add_argument("--apply", action="store_true", help="应用确定性映射及安全的一对一名称规范化")
    parser.add_argument("--output", type=Path, help="将完整 JSON 报告写入指定路径")
    args = parser.parse_args()

    with SessionLocal() as db:
        report = audit_language_mappings(db, apply=args.apply)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
