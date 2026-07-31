"""
清理旧版翻译订单和不再使用的旧版客户。

识别规则：
- 旧订单号：TP-YYMMDD-NNNN（末尾至少四位流水号）
- 旧客户号：CL-YYMMDD-NNNN（旧日期分段且末尾至少四位流水号）

安全策略：
1. 默认只预览，不修改数据库。
2. 先删除旧订单对应的财务记录，再删除旧订单；其余从属记录交给数据库
   已定义的 CASCADE / SET NULL 外键处理。
3. 旧客户仅在清理旧订单后不存在项目、咨询、联系记录或子客户项目引用时删除。
   仍被新订单或其他板块使用的旧客户会保留。

执行方式：
    python cleanup_legacy_projects_clients.py
    python cleanup_legacy_projects_clients.py --apply
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from database import engine


LEGACY_PROJECT_PATTERN = r"^TP-[0-9]{6}-[0-9]{4,}$"
LEGACY_CLIENT_PATTERN = r"^CL-[0-9]{6}-[0-9]{4,}$"
LOCK_NAME = "cleanup_legacy_projects_clients_v1"


@dataclass(frozen=True)
class CleanupSummary:
    legacy_projects: int
    finance_records: int
    finance_payments: int
    deletable_clients: int
    retained_clients: int
    deleted_projects: int = 0
    deleted_finance_records: int = 0
    deleted_clients: int = 0


def _prepare_targets(conn: Connection) -> None:
    """在当前事务中固化目标，避免清理过程中规则集合发生变化。"""
    conn.execute(
        text(
            """
            SELECT pg_advisory_xact_lock(hashtext(:lock_name));

            CREATE TEMP TABLE legacy_project_cleanup_target
            ON COMMIT DROP AS
            SELECT id, order_no
            FROM translation_project
            WHERE order_no ~ :project_pattern;

            CREATE UNIQUE INDEX ON legacy_project_cleanup_target (id);

            CREATE TEMP TABLE legacy_client_cleanup_target
            ON COMMIT DROP AS
            SELECT c.id, c.client_code
            FROM client c
            WHERE c.client_code ~ :client_pattern
              AND NOT EXISTS (
                  SELECT 1
                  FROM translation_project p
                  WHERE p.client_id = c.id
                    AND NOT EXISTS (
                        SELECT 1
                        FROM legacy_project_cleanup_target target
                        WHERE target.id = p.id
                    )
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM consultation consultation_record
                  WHERE consultation_record.client_id = c.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM client_contact contact_record
                  WHERE contact_record.client_id = c.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM sub_client child
                  JOIN translation_project p ON p.sub_client_id = child.id
                  WHERE child.parent_client_id = c.id
                    AND NOT EXISTS (
                        SELECT 1
                        FROM legacy_project_cleanup_target target
                        WHERE target.id = p.id
                    )
              );

            CREATE UNIQUE INDEX ON legacy_client_cleanup_target (id);
            """
        ),
        {
            "lock_name": LOCK_NAME,
            "project_pattern": LEGACY_PROJECT_PATTERN,
            "client_pattern": LEGACY_CLIENT_PATTERN,
        },
    )


def _count(conn: Connection, sql: str) -> int:
    return int(conn.execute(text(sql)).scalar_one())


def _load_preview(conn: Connection) -> tuple[CleanupSummary, list[str], list[str], list[str]]:
    project_numbers = list(
        conn.execute(
            text(
                """
                SELECT order_no
                FROM legacy_project_cleanup_target
                ORDER BY order_no
                """
            )
        ).scalars()
    )
    deletable_clients = list(
        conn.execute(
            text(
                """
                SELECT client_code
                FROM legacy_client_cleanup_target
                ORDER BY client_code
                """
            )
        ).scalars()
    )
    retained_clients = list(
        conn.execute(
            text(
                """
                SELECT c.client_code
                FROM client c
                WHERE c.client_code ~ :client_pattern
                  AND NOT EXISTS (
                      SELECT 1
                      FROM legacy_client_cleanup_target target
                      WHERE target.id = c.id
                  )
                ORDER BY c.client_code
                """
            ),
            {"client_pattern": LEGACY_CLIENT_PATTERN},
        ).scalars()
    )

    summary = CleanupSummary(
        legacy_projects=len(project_numbers),
        finance_records=_count(
            conn,
            """
            SELECT count(*)
            FROM finance_record finance
            JOIN legacy_project_cleanup_target target
              ON target.id = finance.project_id
            """,
        ),
        finance_payments=_count(
            conn,
            """
            SELECT count(*)
            FROM finance_payment payment
            JOIN finance_record finance ON finance.id = payment.finance_id
            JOIN legacy_project_cleanup_target target
              ON target.id = finance.project_id
            """,
        ),
        deletable_clients=len(deletable_clients),
        retained_clients=len(retained_clients),
    )
    return summary, project_numbers, deletable_clients, retained_clients


def cleanup(*, apply: bool = False) -> CleanupSummary:
    with engine.begin() as conn:
        _prepare_targets(conn)
        preview, project_numbers, deletable_clients, retained_clients = _load_preview(conn)

        print(f"旧订单：{preview.legacy_projects} 条")
        print(f"关联财务记录：{preview.finance_records} 条")
        print(f"关联回款记录：{preview.finance_payments} 条")
        print(f"可安全删除旧客户：{preview.deletable_clients} 条")
        print(f"因仍被引用而保留旧客户：{preview.retained_clients} 条")
        if project_numbers:
            print("旧订单范围：" + "、".join(project_numbers))
        if deletable_clients:
            print("待删旧客户：" + "、".join(deletable_clients))
        if retained_clients:
            print("保留旧客户：" + "、".join(retained_clients))

        if not apply:
            print("当前为预览模式，数据库未修改；确认后使用 --apply 执行。")
            return preview

        deleted_finance_records = conn.execute(
            text(
                """
                DELETE FROM finance_record finance
                USING legacy_project_cleanup_target target
                WHERE finance.project_id = target.id
                """
            )
        ).rowcount
        deleted_projects = conn.execute(
            text(
                """
                DELETE FROM translation_project project
                USING legacy_project_cleanup_target target
                WHERE project.id = target.id
                """
            )
        ).rowcount
        deleted_clients = conn.execute(
            text(
                """
                DELETE FROM client client_record
                USING legacy_client_cleanup_target target
                WHERE client_record.id = target.id
                """
            )
        ).rowcount

        result = CleanupSummary(
            legacy_projects=preview.legacy_projects,
            finance_records=preview.finance_records,
            finance_payments=preview.finance_payments,
            deletable_clients=preview.deletable_clients,
            retained_clients=preview.retained_clients,
            deleted_projects=deleted_projects,
            deleted_finance_records=deleted_finance_records,
            deleted_clients=deleted_clients,
        )
        print(
            "清理完成："
            f"删除订单 {result.deleted_projects} 条、"
            f"财务记录 {result.deleted_finance_records} 条、"
            f"客户 {result.deleted_clients} 条。"
        )
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="安全清理旧版订单和无引用旧客户")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际执行删除；不传此参数时仅预览",
    )
    args = parser.parse_args()
    cleanup(apply=args.apply)
