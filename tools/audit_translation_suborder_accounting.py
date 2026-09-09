"""输出笔译子订单字数与母订单级未确认派稿的数据审计结果。"""

from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy import inspect, text

from database import SessionLocal, engine


def _rows(db, statement: str) -> list[dict]:
    return [dict(row) for row in db.execute(text(statement)).mappings().all()]


def build_audit_report() -> dict:
    # 主应用导入会注册所有跨模块 ORM 模型，保证独立运行审计脚本时关系可解析。
    import main as _application_models  # noqa: F401
    from crud import get_translation_project
    from schemas import TranslationProjectResponse

    inspector = inspect(engine)
    arrangement_columns = {
        column["name"] for column in inspector.get_columns("manuscript_arrangement")
    }
    with SessionLocal() as db:
        empty_sub_orders = _rows(
            db,
            """
            SELECT s.id, s.sub_order_no, s.sub_project_name,
                   p.id AS project_id, p.order_no AS project_order_no
              FROM translation_sub_order s
              JOIN translation_project p ON p.id = s.parent_project_id
             WHERE NOT EXISTS (
                   SELECT 1 FROM word_count_metric w
                    WHERE w.sub_order_id = s.id
                      AND w.dimension IN ('company', 'customer', 'translator_estimate')
                      AND w.count_value IS NOT NULL
             )
             ORDER BY p.order_no, s.sub_order_no
            """,
        )
        metric_rows = _rows(
            db,
            """
            SELECT p.id AS project_id, p.order_no AS project_order_no,
                   s.id AS sub_order_id, s.sub_order_no,
                   w.project_id AS metric_project_id, w.sub_order_id AS metric_sub_order_id,
                   w.dimension, w.metric_type, w.count_value
              FROM translation_project p
              JOIN translation_sub_order s ON s.parent_project_id = p.id
              LEFT JOIN word_count_metric w
                ON w.project_id = p.id OR w.sub_order_id = s.id
             ORDER BY p.order_no, s.sub_order_no
            """,
        )
        parent_level_drafts = _rows(
            db,
            """
            SELECT d.id AS dispatch_id, d.translation_project_id AS project_id,
                   p.order_no AS project_order_no, p.project_name,
                   d.status, d.created_at
              FROM manuscript_dispatch d
              JOIN translation_project p ON p.id = d.translation_project_id
             WHERE d.sub_order_id IS NULL
               AND d.confirmed_at IS NULL
               AND d.status = 'draft'
               AND EXISTS (
                   SELECT 1 FROM translation_sub_order s
                    WHERE s.parent_project_id = p.id
               )
             ORDER BY d.created_at, p.order_no
            """,
        )
        sample_project_id = (
            empty_sub_orders[0]["project_id"]
            if empty_sub_orders
            else db.execute(text("SELECT id FROM translation_project LIMIT 1")).scalar()
        )
        application_probe = None
        if sample_project_id:
            project = get_translation_project(db, sample_project_id)
            response = TranslationProjectResponse.model_validate(project)
            application_probe = {
                "project_order_no": response.order_no,
                "word_count_matrix_source": response.word_count_matrix_source,
                "word_count_sub_order_count": response.word_count_sub_order_count,
                "sub_order_count": len(response.sub_orders),
            }

    projects: dict = defaultdict(lambda: {"parent": {}, "children": defaultdict(dict), "meta": {}})
    for row in metric_rows:
        project = projects[row["project_id"]]
        project["meta"] = {
            "project_id": row["project_id"],
            "project_order_no": row["project_order_no"],
        }
        project["children"].setdefault(row["sub_order_id"], {})
        if row["dimension"] is None:
            continue
        key = f'{row["dimension"]}.{row["metric_type"]}'
        if row["metric_project_id"] is not None:
            project["parent"][key] = row["count_value"]
        elif row["metric_sub_order_id"] is not None:
            project["children"][row["sub_order_id"]][key] = row["count_value"]

    identical_word_counts = []
    for project in projects.values():
        child_matrices = list(project["children"].values())
        if (
            len(child_matrices) >= 2
            and project["parent"]
            and all(matrix == project["parent"] for matrix in child_matrices)
        ):
            identical_word_counts.append({
                **project["meta"],
                "sub_order_count": len(child_matrices),
                "word_count_matrix": project["parent"],
            })

    return {
        "schema": {
            "translation_sub_order_charge_item": inspector.has_table(
                "translation_sub_order_charge_item"
            ),
            "manuscript_arrangement_file": inspector.has_table(
                "manuscript_arrangement_file"
            ),
            "manuscript_arrangement_file_selection_mode": (
                "file_selection_mode" in arrangement_columns
            ),
        },
        "application_probe": application_probe,
        "empty_sub_order_word_counts": empty_sub_orders,
        "all_sub_orders_equal_parent_word_counts": identical_word_counts,
        "unconfirmed_parent_level_dispatches": parent_level_drafts,
        "summary": {
            "empty_sub_order_word_count_count": len(empty_sub_orders),
            "all_sub_orders_equal_parent_project_count": len(identical_word_counts),
            "unconfirmed_parent_level_dispatch_count": len(parent_level_drafts),
        },
    }


if __name__ == "__main__":
    print(json.dumps(build_audit_report(), ensure_ascii=False, indent=2, default=str))
