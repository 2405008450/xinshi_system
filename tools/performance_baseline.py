"""只读采样核心列表的 SQL 数、耗时与序列化体积。"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

from sqlalchemy import event


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from annotation_schemas import AnnotationProjectListResponse
from annotation_service import count_annotation_projects, get_annotation_projects
from crud import (
    count_clients,
    count_consultations,
    count_translation_projects,
    get_clients,
    get_consultations,
    get_translation_projects,
)
from database import SessionLocal, engine
from interpretation_schemas import InterpretationProjectListResponse
from interpretation_service import count_interpretation_projects, get_interpretation_projects
from recruitment_schemas import RecruitmentProjectResponse
from recruitment_service import count_recruitment_projects, get_recruitment_projects
from resource_request_schemas import ResourceRequestResponse
from resource_request_service import count_resource_requests, list_resource_requests
from resource_schemas import ResourcePersonListResponse
from resource_service import count_talents, get_talents
from schemas import ClientResponse, ConsultationResponse, TranslationProjectResponse


CASES = (
    ("translation", get_translation_projects, count_translation_projects, TranslationProjectResponse),
    ("annotation", get_annotation_projects, count_annotation_projects, AnnotationProjectListResponse),
    ("interpretation", get_interpretation_projects, count_interpretation_projects, InterpretationProjectListResponse),
    ("recruitment", get_recruitment_projects, count_recruitment_projects, RecruitmentProjectResponse),
    ("talents", get_talents, count_talents, ResourcePersonListResponse),
    ("clients", get_clients, count_clients, ClientResponse),
    ("consultations", get_consultations, count_consultations, ConsultationResponse),
    ("resource_requests", list_resource_requests, count_resource_requests, ResourceRequestResponse),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit 必须在 1～100 之间")
    if not 1 <= args.repeats <= 20:
        parser.error("--repeats 必须在 1～20 之间")

    query_counter = {"value": 0, "tables": {}}

    def count_query(_conn, _cursor, statement, *_args, **_kwargs):
        query_counter["value"] += 1
        names = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)", statement, re.I)
        summary = "+".join(dict.fromkeys(name.lower() for name in names)) or "other"
        tables = query_counter["tables"]
        tables[summary] = tables.get(summary, 0) + 1

    event.listen(engine, "before_cursor_execute", count_query)
    output: dict[str, dict] = {}
    try:
        for name, list_fn, count_fn, schema in CASES:
            samples = []
            for _ in range(args.repeats):
                db = SessionLocal()
                try:
                    query_counter["value"] = 0
                    query_counter["tables"] = {}
                    started = time.perf_counter()
                    rows = list_fn(db, skip=0, limit=args.limit)
                    listed = time.perf_counter()
                    payload = [schema.model_validate(row).model_dump(mode="json") for row in rows]
                    serialized = time.perf_counter()
                    list_sql = query_counter["value"]
                    list_sql_tables = query_counter["tables"]
                    query_counter["value"] = 0
                    query_counter["tables"] = {}
                    count_started = time.perf_counter()
                    total = count_fn(db)
                    count_finished = time.perf_counter()
                    samples.append({
                        "rows": len(rows),
                        "total": int(total),
                        "list_sql": list_sql,
                        "list_sql_tables": list_sql_tables,
                        "list_ms": round((listed - started) * 1000, 2),
                        "serialize_ms": round((serialized - listed) * 1000, 2),
                        "payload_bytes": len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
                        "count_sql": query_counter["value"],
                        "count_ms": round((count_finished - count_started) * 1000, 2),
                    })
                finally:
                    db.close()
            output[name] = {
                "median_list_ms": round(statistics.median(item["list_ms"] for item in samples), 2),
                "max_list_sql": max(item["list_sql"] for item in samples),
                "samples": samples,
            }
    finally:
        event.remove(engine, "before_cursor_execute", count_query)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
