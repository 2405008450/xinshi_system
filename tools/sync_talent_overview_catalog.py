"""将当前人才概览中的具体语种同步到共享目录；默认仅预览。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import main as _application_models  # noqa: E402,F401
from database import SessionLocal  # noqa: E402
from talent_overview_service import get_talent_overview, sync_overview_language_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="同步人才概览与共享语种目录")
    parser.add_argument("--apply", action="store_true", help="提交新增及关联")
    args = parser.parse_args()
    with SessionLocal() as db:
        result = sync_overview_language_catalog(db, get_talent_overview(db))
        if args.apply:
            db.commit()
        else:
            db.rollback()
    print(json.dumps({"applied": args.apply, **result}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
