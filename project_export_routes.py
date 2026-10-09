"""项目模块共用的只读导出路由注册。"""

import json
from datetime import date
from io import BytesIO
from typing import Literal, Optional
from urllib.parse import quote
from uuid import UUID

from fastapi import Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from project_export_service import (
    MODULE_LABELS, TIME_FIELDS, ProjectExportEmptyError, ProjectExportLimitError,
    create_project_export,
)


def build_export_filters(module, parser, db, *, time_field=None, date_start=None, date_end=None,
                         keyword=None, field_filters=None, client_id=None, order_scope="parent",
                         parent_project_id=None, sort=None):
    if client_id is not None:
        # 按母客户精确导出，不混入当前列表的筛选、分页或时间条件。
        result = {"client_id": client_id}
        if module == "annotation":
            result["order_scope"] = "all"
        return result
    if time_field not in TIME_FIELDS[module]:
        raise HTTPException(status_code=422, detail="请选择有效的时间口径")
    if date_start is None or date_end is None:
        raise HTTPException(status_code=422, detail="请选择完整的时间范围")
    if date_start > date_end:
        raise HTTPException(status_code=422, detail="开始日期不能晚于结束日期")
    specs = parser(field_filters, db)
    specs[time_field] = {"op": "between", "from": date_start.isoformat(), "to": date_end.isoformat()}
    specs = parser(json.dumps(specs, ensure_ascii=False), db)
    result = {"keyword": keyword, "field_filters": specs}
    if module == "annotation":
        if sort not in (None, "order_no_desc", "latest_progress_desc"):
            raise HTTPException(status_code=422, detail="不支持的排序方式")
        result.update(order_scope=order_scope, parent_project_id=parent_project_id, sort=sort or "order_no_desc")
    elif sort is not None:
        raise HTTPException(status_code=422, detail="该模块沿用列表默认排序")
    return result


def export_response(db, module, mode, filters, *, time_field=None, date_start=None, date_end=None, client_id=None):
    try:
        content = create_project_export(db, module, mode, filters)
    except ProjectExportEmptyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProjectExportLimitError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    suffix = {"projects": "导出", "reconciliation": "客户对账单",
              "personnel": "人员对账单" if module == "annotation" else "译员对账单",
              "candidates": "候选人跟进明细"}[mode]
    scope = f"客户_{client_id}" if client_id else f"{TIME_FIELDS[module][time_field]}_{date_start}_至_{date_end}"
    filename = f"{MODULE_LABELS[module]}{suffix}_{scope}.xlsx"
    return StreamingResponse(BytesIO(content), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{module}-{mode}.xlsx"; filename*=UTF-8\'\'{quote(filename)}'})


def register_project_exports(router, module, parser):
    def endpoint(mode, allow_client=False):
        def export(
            time_field: Optional[str] = None,
            date_start: Optional[date] = None,
            date_end: Optional[date] = None,
            keyword: Optional[str] = None,
            field_filters: Optional[str] = Query(None),
            client_id: Optional[UUID] = None,
            order_scope: Literal["parent", "child", "all"] = "parent",
            parent_project_id: Optional[UUID] = None,
            sort: Optional[str] = None,
            db: Session = Depends(get_db),
        ):
            if client_id is not None and not allow_client:
                raise HTTPException(status_code=422, detail="此导出类型需要选择时间范围")
            filters = build_export_filters(
                module, parser, db, time_field=time_field, date_start=date_start, date_end=date_end,
                keyword=keyword, field_filters=field_filters, client_id=client_id,
                order_scope=order_scope, parent_project_id=parent_project_id, sort=sort,
            )
            return export_response(db, module, mode, filters, time_field=time_field,
                                   date_start=date_start, date_end=date_end, client_id=client_id)
        return export
    router.add_api_route("/export", endpoint("projects"), methods=["GET"], name=f"{module}_project_export")
    router.add_api_route("/reconciliation-export", endpoint("reconciliation", True), methods=["GET"], name=f"{module}_reconciliation_export")
    path, mode = {
        "interpretation": ("translator-reconciliation-export", "personnel"),
        "annotation": ("personnel-reconciliation-export", "personnel"),
        "recruitment": ("candidate-tracking-export", "candidates"),
    }[module]
    router.add_api_route(f"/{path}", endpoint(mode), methods=["GET"], name=f"{module}_{mode}_export")
