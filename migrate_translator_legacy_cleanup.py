"""
迁移脚本：将 translator 表中的旧合并字段回填到拆分字段，并可选删除旧列。

默认行为：
1. 确保拆分字段存在
2. 用 cloud_revision / daily_rate 回填 can_cloud_edit / can_revision /
   daily_accept_count / hourly_speed / daily_word_capacity
3. 不删除旧列

如需删除旧列，请显式执行：
python migrate_translator_legacy_cleanup.py --drop-legacy
"""
from __future__ import annotations

import argparse

from sqlalchemy import text

from database import engine


def _parse_bool_label(value: str):
    normalized = (value or "").strip()
    if normalized in {"可", "是", "true", "True", "1"}:
        return True
    if normalized in {"否", "不可", "不可以", "false", "False", "0"}:
        return False
    return None


def _parse_int_part(value: str):
    normalized = (value or "").strip()
    if not normalized:
        return None
    try:
        return int(float(normalized))
    except (TypeError, ValueError):
        return None


def migrate(drop_legacy: bool = False):
    ensure_columns_sql = """
    ALTER TABLE translator
        ADD COLUMN IF NOT EXISTS can_cloud_edit BOOLEAN,
        ADD COLUMN IF NOT EXISTS can_revision BOOLEAN,
        ADD COLUMN IF NOT EXISTS daily_accept_count INTEGER,
        ADD COLUMN IF NOT EXISTS hourly_speed INTEGER,
        ADD COLUMN IF NOT EXISTS daily_word_capacity INTEGER;
    """

    select_sql = text("""
        SELECT
            id,
            cloud_revision,
            daily_rate,
            can_cloud_edit,
            can_revision,
            daily_accept_count,
            hourly_speed,
            daily_word_capacity
        FROM translator
    """)

    update_sql = text("""
        UPDATE translator
        SET
            can_cloud_edit = COALESCE(:can_cloud_edit, can_cloud_edit),
            can_revision = COALESCE(:can_revision, can_revision),
            daily_accept_count = COALESCE(:daily_accept_count, daily_accept_count),
            hourly_speed = COALESCE(:hourly_speed, hourly_speed),
            daily_word_capacity = COALESCE(:daily_word_capacity, daily_word_capacity)
        WHERE id = :translator_id
    """)

    drop_sql = """
    ALTER TABLE translator
        DROP COLUMN IF EXISTS cloud_revision,
        DROP COLUMN IF EXISTS daily_rate;
    """

    updated_rows = 0
    with engine.begin() as conn:
        conn.execute(text(ensure_columns_sql))
        rows = conn.execute(select_sql).mappings().all()
        for row in rows:
            updates = {
                "translator_id": row["id"],
                "can_cloud_edit": None,
                "can_revision": None,
                "daily_accept_count": None,
                "hourly_speed": None,
                "daily_word_capacity": None,
            }

            cloud_revision = (row["cloud_revision"] or "").strip()
            if cloud_revision and (row["can_cloud_edit"] is None or row["can_revision"] is None):
                left, right, *_ = [part.strip() for part in cloud_revision.split("/")] + ["", ""]
                if row["can_cloud_edit"] is None:
                    updates["can_cloud_edit"] = _parse_bool_label(left)
                if row["can_revision"] is None:
                    updates["can_revision"] = _parse_bool_label(right)

            daily_rate = (row["daily_rate"] or "").strip()
            if daily_rate and (
                row["daily_accept_count"] is None
                or row["hourly_speed"] is None
                or row["daily_word_capacity"] is None
            ):
                first, second, third, *_ = [part.strip() for part in daily_rate.split("/")] + ["", "", ""]
                if row["daily_accept_count"] is None:
                    updates["daily_accept_count"] = _parse_int_part(first)
                if row["hourly_speed"] is None:
                    updates["hourly_speed"] = _parse_int_part(second)
                if row["daily_word_capacity"] is None:
                    updates["daily_word_capacity"] = _parse_int_part(third)

            if any(value is not None for key, value in updates.items() if key != "translator_id"):
                conn.execute(update_sql, updates)
                updated_rows += 1

        if drop_legacy:
            conn.execute(text(drop_sql))

    print(f"Translator legacy cleanup completed. Backfilled rows: {updated_rows}.")
    if drop_legacy:
        print("Legacy columns dropped: cloud_revision, daily_rate")
    else:
        print("Legacy columns kept for safety. Re-run with --drop-legacy to remove them.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop-legacy", action="store_true", help="删除旧列 cloud_revision / daily_rate")
    args = parser.parse_args()
    migrate(drop_legacy=args.drop_legacy)
