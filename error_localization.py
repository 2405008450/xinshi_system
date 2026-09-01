"""面向接口调用方的校验错误中文化。"""

from __future__ import annotations

from typing import Any


HTTP_STATUS_MESSAGES = {
    400: "请求内容有误，请检查后重试",
    401: "登录状态已失效，请重新登录",
    403: "没有权限执行此操作",
    404: "请求的内容不存在或已被删除",
    408: "请求超时，请稍后重试",
    409: "数据状态已发生变化，请刷新后重试",
    422: "提交内容校验失败，请检查后重试",
    429: "操作过于频繁，请稍后重试",
    500: "服务暂时异常，请稍后重试",
    502: "上游服务暂时不可用，请稍后重试",
    503: "服务暂时不可用，请稍后重试",
}

TECHNICAL_MARKERS = (
    "axios",
    "pydantic",
    "sqlalchemy",
    "integrityerror",
    "operationalerror",
    "traceback",
    "validationerror",
    "field required",
    "network error",
    "request failed with status code",
)


def _has_chinese(value: str) -> bool:
    return any("\u3400" <= char <= "\u9fff" for char in value)


def _safe_http_message(value: Any, status_code: int) -> str:
    fallback = HTTP_STATUS_MESSAGES.get(status_code, "请求处理失败，请稍后重试")
    if not isinstance(value, str) or not value.strip():
        return fallback
    message = value.strip()
    lower_message = message.lower()
    if any(marker in lower_message for marker in TECHNICAL_MARKERS):
        return fallback
    if not _has_chinese(message) and any(char.isalpha() for char in message):
        return fallback
    return message


def localize_http_detail(detail: Any, status_code: int) -> Any:
    """清理 HTTP 异常展示内容，同时保留结构化业务错误的附加字段。"""
    if isinstance(detail, str):
        return _safe_http_message(detail, status_code)
    if isinstance(detail, dict):
        localized = dict(detail)
        if "message" in localized:
            localized["message"] = _safe_http_message(localized["message"], status_code)
        if "detail" in localized and isinstance(localized["detail"], str):
            localized["detail"] = _safe_http_message(localized["detail"], status_code)
        return localized
    return detail


def _limit(ctx: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in ctx:
            return ctx[key]
    return default


def localize_validation_message(error: dict[str, Any]) -> str:
    """根据 Pydantic 错误类型生成稳定中文，避免依赖英文原始 msg。"""
    error_type = str(error.get("type") or "")
    ctx = error.get("ctx") or {}

    if error_type == "missing":
        return "此字段为必填项"
    if "string_too_short" in error_type:
        return f"内容不能少于 {_limit(ctx, 'min_length', 'minLength', default=1)} 个字符"
    if "string_too_long" in error_type:
        return f"内容不能超过 {_limit(ctx, 'max_length', 'maxLength')} 个字符"
    if "too_short" in error_type:
        return f"至少需要 {_limit(ctx, 'min_length', 'minLength', default=1)} 项"
    if "too_long" in error_type:
        return f"最多允许 {_limit(ctx, 'max_length', 'maxLength')} 项"
    if "greater_than_equal" in error_type:
        return f"数值不能小于 {_limit(ctx, 'ge', 'limit_value')}"
    if "greater_than" in error_type:
        return f"数值必须大于 {_limit(ctx, 'gt', 'limit_value')}"
    if "less_than_equal" in error_type:
        return f"数值不能大于 {_limit(ctx, 'le', 'limit_value')}"
    if "less_than" in error_type:
        return f"数值必须小于 {_limit(ctx, 'lt', 'limit_value')}"
    if "date" in error_type or "datetime" in error_type or "time" in error_type:
        return "日期时间格式不正确"
    if "uuid" in error_type:
        return "标识格式不正确"
    if "email" in error_type:
        return "邮箱格式不正确"
    if "url" in error_type:
        return "网址格式不正确"
    if "list" in error_type or "array" in error_type or "tuple" in error_type or "set" in error_type:
        return "应提交有效列表"
    if any(item in error_type for item in ("int", "float", "decimal", "number")):
        return "应提交有效数字"
    if "bool" in error_type:
        return "应提交有效状态值"
    if "literal" in error_type or "enum" in error_type:
        return "选项值无效"
    if error_type.startswith("value_error"):
        message = str(error.get("msg") or "")
        if any("\u3400" <= char <= "\u9fff" for char in message):
            return message.removeprefix("Value error, ").removeprefix("值错误，")
        return "内容不符合业务规则"
    return "内容格式不正确"


def localize_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """保持 FastAPI 默认错误结构，仅替换可展示的 msg。"""
    localized: list[dict[str, Any]] = []
    for error in errors:
        item = dict(error)
        item["msg"] = localize_validation_message(item)
        localized.append(item)
    return localized
