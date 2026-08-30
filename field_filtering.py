"""列表字段筛选的公共解析、校验与 SQLAlchemy 标量条件构造。"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from typing import Any, Mapping, Optional
from uuid import UUID

from fastapi import HTTPException, status


ALLOWED_OPERATORS = {"contains", "in", "between", "eq"}
MAX_FILTER_FIELDS = 100
MAX_IN_VALUES = 100
MAX_TEXT_LENGTH = 500


def parse_field_filters(raw: Optional[str]) -> dict[str, dict[str, Any]]:
    """解析 GET 查询参数中的 JSON；所有无效输入统一返回可读的 422。"""
    if raw is None or not str(raw).strip():
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="field_filters 必须是合法的 JSON 对象",
        ) from exc
    if not isinstance(value, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="field_filters 必须是对象",
        )
    if len(value) > MAX_FILTER_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"field_filters 最多允许 {MAX_FILTER_FIELDS} 个字段",
        )

    parsed: dict[str, dict[str, Any]] = {}
    for field, descriptor in value.items():
        if not isinstance(field, str) or not field.strip():
            raise HTTPException(status_code=422, detail="field_filters 字段名不能为空")
        if not isinstance(descriptor, dict):
            raise HTTPException(status_code=422, detail=f"字段 {field} 的筛选描述必须是对象")
        operator = descriptor.get("op")
        if operator not in ALLOWED_OPERATORS:
            raise HTTPException(status_code=422, detail=f"字段 {field} 使用了不支持的操作符")
        normalized = dict(descriptor)
        if operator in {"contains", "eq"}:
            if "value" not in descriptor:
                raise HTTPException(status_code=422, detail=f"字段 {field} 缺少 value")
            if isinstance(descriptor.get("value"), str) and len(descriptor["value"]) > MAX_TEXT_LENGTH:
                raise HTTPException(status_code=422, detail=f"字段 {field} 的文本过长")
        elif operator == "in":
            values = descriptor.get("value")
            if not isinstance(values, list) or not values:
                raise HTTPException(status_code=422, detail=f"字段 {field} 的 in 值必须是非空数组")
            if len(values) > MAX_IN_VALUES:
                raise HTTPException(status_code=422, detail=f"字段 {field} 的候选值过多")
        elif operator == "between":
            if not any(descriptor.get(key) not in (None, "") for key in ("from", "to", "min", "max")):
                raise HTTPException(status_code=422, detail=f"字段 {field} 的范围不能为空")
        parsed[field.strip()] = normalized
    return parsed


def ensure_filter_fields(
    filters: Mapping[str, dict[str, Any]], allowed_fields: set[str], *, allow_custom: bool = False
) -> None:
    unknown = [
        key for key in filters
        if key not in allowed_fields and not (allow_custom and key.startswith("custom:"))
    ]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"不支持的筛选字段：{'、'.join(unknown)}",
        )


def ensure_filter_operators(
    filters: Mapping[str, dict[str, Any]],
    rules: Mapping[str, set[str]],
    *,
    allow_custom: bool = False,
) -> None:
    """校验业务字段可使用的操作符，防止合法字段搭配错误操作符后被静默忽略。"""
    for field, descriptor in filters.items():
        if allow_custom and field.startswith("custom:"):
            continue
        allowed = rules.get(field, set())
        operator = descriptor.get("op")
        if operator not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"字段 {field} 不支持操作符 {operator}",
            )


def _coerce(value: Any, value_type: str) -> Any:
    if value is None or value == "":
        return None
    try:
        if value_type == "number":
            return float(value)
        if value_type == "integer":
            return int(value)
        if value_type == "boolean":
            if isinstance(value, bool):
                return value
            normalized = str(value).strip().lower()
            if normalized in {"1", "true", "yes"}:
                return True
            if normalized in {"0", "false", "no"}:
                return False
            raise ValueError
        if value_type == "uuid":
            return UUID(str(value))
        if value_type in {"date", "datetime"}:
            return date.fromisoformat(str(value)[:10])
        return str(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="筛选值格式不正确") from exc


def apply_scalar_filter(query, expression, descriptor: Mapping[str, Any], *, value_type: str = "string"):
    """对普通列应用 contains/in/eq/between，复杂关联字段由各业务服务自行处理。"""
    operator = descriptor["op"]
    if operator == "contains":
        if value_type != "string":
            raise HTTPException(status_code=422, detail="该字段不支持包含匹配")
        value = str(descriptor.get("value") or "").strip()
        return query if not value else query.filter(expression.ilike(f"%{value}%"))
    if operator == "eq":
        return query.filter(expression == _coerce(descriptor.get("value"), value_type))
    if operator == "in":
        values = [_coerce(item, value_type) for item in descriptor.get("value", [])]
        return query.filter(expression.in_(values))
    if operator != "between":
        raise HTTPException(status_code=422, detail="该字段不支持此筛选操作")

    lower = descriptor.get("from", descriptor.get("min"))
    upper = descriptor.get("to", descriptor.get("max"))
    lower_value = _coerce(lower, value_type)
    upper_value = _coerce(upper, value_type)
    if value_type == "datetime":
        if lower_value is not None:
            query = query.filter(expression >= datetime.combine(lower_value, time.min))
        if upper_value is not None:
            query = query.filter(expression < datetime.combine(upper_value + timedelta(days=1), time.min))
        return query
    if lower_value is not None:
        query = query.filter(expression >= lower_value)
    if upper_value is not None:
        query = query.filter(expression <= upper_value)
    return query


def apply_scalar_specs(query, filters: Mapping[str, dict[str, Any]], specs: Mapping[str, tuple[Any, str]]):
    for field, descriptor in filters.items():
        spec = specs.get(field)
        if spec is None:
            continue
        expression, value_type = spec
        query = apply_scalar_filter(query, expression, descriptor, value_type=value_type)
    return query
