"""标注动态字段定义、取值规范化与查询表达式。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import Date as SqlDate, DateTime as SqlDateTime, Numeric, String, cast
from sqlalchemy.orm import Session

from annotation_ops_models import AnnotationCustomFieldDefinition


PROJECT_SCOPED_TABLES = {"trial", "assignment"}
GLOBAL_SCOPED_TABLES = {"project", "account"}
ALLOWED_TABLES = PROJECT_SCOPED_TABLES | GLOBAL_SCOPED_TABLES


def _validate_scope(table_code: str, project_id: Optional[UUID]) -> None:
    if table_code not in ALLOWED_TABLES:
        raise ValueError("不支持的动态字段业务表")
    if table_code in PROJECT_SCOPED_TABLES and project_id is None:
        raise ValueError("试标和正式安排动态字段必须指定项目")
    if table_code in GLOBAL_SCOPED_TABLES and project_id is not None:
        raise ValueError("项目和账号动态字段必须是全局字段，不能指定项目")


def list_custom_fields(db: Session, table_code: str, project_id: Optional[UUID], include_inactive: bool = False):
    _validate_scope(table_code, project_id)
    query = db.query(AnnotationCustomFieldDefinition).filter(
        AnnotationCustomFieldDefinition.table_code == table_code,
        AnnotationCustomFieldDefinition.project_id.is_(None) if project_id is None else AnnotationCustomFieldDefinition.project_id == project_id,
    )
    if not include_inactive:
        query = query.filter(AnnotationCustomFieldDefinition.is_active.is_(True))
    return query.order_by(AnnotationCustomFieldDefinition.sequence_no).all()


def _resequence(db: Session, table_code: str, project_id: Optional[UUID], ordered_ids: list[UUID]) -> None:
    rows = list_custom_fields(db, table_code, project_id, include_inactive=True)
    by_id = {row.id: row for row in rows}
    for index, row in enumerate(rows, start=1):
        row.sequence_no = -index
    db.flush()
    for index, field_id in enumerate(ordered_ids, start=1):
        by_id[field_id].sequence_no = index


def create_custom_field(db: Session, payload, created_by: Optional[UUID]):
    _validate_scope(payload.table_code, payload.project_id)
    rows = list_custom_fields(db, payload.table_code, payload.project_id, include_inactive=True)
    position = min(payload.sequence_no or len(rows) + 1, len(rows) + 1)
    row = AnnotationCustomFieldDefinition(**payload.model_dump(exclude={"sequence_no"}), sequence_no=len(rows) + 1, created_by=created_by)
    db.add(row)
    db.flush()
    ids = [item.id for item in rows]
    ids.insert(position - 1, row.id)
    _resequence(db, payload.table_code, payload.project_id, ids)
    db.commit()
    db.refresh(row)
    return row


def update_custom_field(db: Session, field_id: UUID, payload):
    row = db.get(AnnotationCustomFieldDefinition, field_id)
    if not row:
        return None
    if payload.table_code != row.table_code or payload.project_id != row.project_id:
        raise ValueError("动态字段创建后不能变更所属业务表或项目")
    rows = list_custom_fields(db, row.table_code, row.project_id, include_inactive=True)
    for key, value in payload.model_dump(exclude={"sequence_no"}).items():
        setattr(row, key, value)
    row.updated_at = datetime.now()
    ordered = [item.id for item in rows if item.id != row.id]
    position = min(payload.sequence_no or row.sequence_no, len(ordered) + 1)
    ordered.insert(position - 1, row.id)
    _resequence(db, row.table_code, row.project_id, ordered)
    db.commit()
    db.refresh(row)
    return row


def deactivate_custom_field(db: Session, field_id: UUID) -> bool:
    row = db.get(AnnotationCustomFieldDefinition, field_id)
    if not row:
        return False
    row.is_active = False
    row.updated_at = datetime.now()
    db.commit()
    return True


def _option_values(options: list[Any]) -> set[Any]:
    return {item.get("value") if isinstance(item, dict) else item for item in options}


def _normalize_value(definition: AnnotationCustomFieldDefinition, value: Any) -> Any:
    if value is None or value == "":
        return None
    data_type = definition.data_type
    if data_type in {"text", "url"}:
        normalized = str(value).strip()
        if data_type == "url" and urlparse(normalized).scheme not in {"http", "https"}:
            raise ValueError(f"{definition.field_label} 必须是 http/https 地址")
        return normalized
    if data_type == "number":
        try:
            return float(Decimal(str(value)))
        except InvalidOperation as exc:
            raise ValueError(f"{definition.field_label} 必须是数字") from exc
    if data_type == "boolean":
        if isinstance(value, bool):
            return value
        if str(value).lower() in {"true", "1", "yes"}:
            return True
        if str(value).lower() in {"false", "0", "no"}:
            return False
        raise ValueError(f"{definition.field_label} 必须是布尔值")
    if data_type in {"date", "datetime"}:
        try:
            parsed = date.fromisoformat(str(value)) if data_type == "date" else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.isoformat()
        except ValueError as exc:
            raise ValueError(f"{definition.field_label} 日期格式无效") from exc
    allowed = _option_values(definition.options)
    if data_type == "single_select":
        if value not in allowed:
            raise ValueError(f"{definition.field_label} 选项无效")
        return value
    if not isinstance(value, list) or any(item not in allowed for item in value):
        raise ValueError(f"{definition.field_label} 多选值无效")
    return list(dict.fromkeys(value))


def validate_custom_values(
    db: Session,
    table_code: str,
    project_id: Optional[UUID],
    values: dict[str, Any],
    existing_values: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """校验动态字段，并在编辑时保留已经停用的历史值。"""
    active_definitions = list_custom_fields(db, table_code, project_id)
    all_definitions = list_custom_fields(db, table_code, project_id, include_inactive=True)
    by_id = {str(item.id): item for item in all_definitions}
    unknown = set(values) - set(by_id)
    if unknown:
        raise ValueError("动态字段值包含不存在的字段")

    existing_values = existing_values or {}
    normalized: dict[str, Any] = {}
    for key, value in values.items():
        definition = by_id[key]
        if not definition.is_active:
            if key not in existing_values or existing_values[key] != value:
                raise ValueError(f"动态字段“{definition.field_label}”已停用，不能修改")
            normalized[key] = existing_values[key]
        else:
            normalized[key] = _normalize_value(definition, value)
    for key, value in existing_values.items():
        definition = by_id.get(key)
        if definition is not None and not definition.is_active and key not in normalized:
            normalized[key] = value

    missing = [
        item.field_label for item in active_definitions
        if item.is_required and (
            normalized.get(str(item.id)) is None
            or normalized.get(str(item.id)) == ""
            or normalized.get(str(item.id)) == []
        )
    ]
    if missing:
        raise ValueError(f"必填动态字段未填写：{'、'.join(missing)}")
    return normalized


def apply_custom_field_filter(query, model, definition: AnnotationCustomFieldDefinition, value: Any):
    expression = model.custom_values[str(definition.id)].astext
    if definition.data_type == "number":
        expression = cast(expression, Numeric)
    elif definition.data_type == "date":
        expression = cast(expression, SqlDate)
    elif definition.data_type == "datetime":
        expression = cast(expression, SqlDateTime)
    elif definition.data_type == "boolean":
        return query.filter(expression == ("true" if bool(value) else "false"))
    else:
        expression = cast(expression, String)
    return query.filter(expression == value)


def apply_custom_field_sort(query, model, definition: AnnotationCustomFieldDefinition, descending: bool = False):
    expression = model.custom_values[str(definition.id)].astext
    if definition.data_type == "number":
        expression = cast(expression, Numeric)
    elif definition.data_type == "date":
        expression = cast(expression, SqlDate)
    elif definition.data_type == "datetime":
        expression = cast(expression, SqlDateTime)
    return query.order_by(expression.desc() if descending else expression.asc())
