"""标注项目历史数据迁移命令。

执行前应先应用 ``data/migrations/20260811_add_annotation_projects.sql``。
脚本可重复运行；已迁移记录会跳过，不会生成重复标注项目。
"""

from sqlalchemy.orm import Session

from annotation_service import (
    ensure_translation_languages_in_catalog,
    migrate_legacy_annotation_projects,
)
from database import engine
from interpretation_service import ensure_default_interpretation_languages


def main() -> None:
    with Session(engine) as db:
        ensure_default_interpretation_languages(db)
        added_languages = ensure_translation_languages_in_catalog(db)
        result = migrate_legacy_annotation_projects(db)
    print(f"共享语种新增：{added_languages}")
    print(
        "迁移完成："
        f"成功 {result['migrated']}，跳过 {result['skipped']}，失败 {result['failed']}"
    )


if __name__ == "__main__":
    main()
