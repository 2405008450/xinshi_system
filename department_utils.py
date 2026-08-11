"""部门名称兼容处理。"""

from typing import Optional


DEPARTMENT_ALIASES = {
    "招聘项目": "其他",
    "翻译部": "IT部",
}


def normalize_department(value: Optional[str]) -> Optional[str]:
    """将历史部门名称转换为当前名称。"""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return ""
    return DEPARTMENT_ALIASES.get(normalized, normalized)


def department_filter_values(value: str) -> tuple[str, ...]:
    """返回查询某部门时需要兼容的当前值和历史值。"""
    normalized = normalize_department(value) or ""
    legacy_values = [
        legacy
        for legacy, current in DEPARTMENT_ALIASES.items()
        if current == normalized
    ]
    return tuple(dict.fromkeys([normalized, *legacy_values]))
