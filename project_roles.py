"""项目固定角色与工作流阶段角色的统一定义。"""

from __future__ import annotations


PROJECT_ROLE_DEFINITIONS = (
    {"role_code": "project_manager", "role_name": "项目经理"},
    {"role_code": "project_specialist", "role_name": "项目专员"},
    {"role_code": "project_assistant", "role_name": "项目助理"},
    {"role_code": "layout_specialist", "role_name": "排版专员"},
)

PROJECT_ROLE_BY_CODE = {
    item["role_code"]: item for item in PROJECT_ROLE_DEFINITIONS
}
PROJECT_ROLE_NAME_BY_CODE = {
    item["role_code"]: item["role_name"] for item in PROJECT_ROLE_DEFINITIONS
}
PROJECT_ROLE_CODE_BY_NAME = {
    item["role_name"]: item["role_code"] for item in PROJECT_ROLE_DEFINITIONS
}

# 项目经理沿用 translation_project.project_manager_id；其余角色存入关系表。
RELATION_ROLE_CODES = frozenset(
    {"project_specialist", "project_assistant", "layout_specialist"}
)

STAGE_ROLE_DEFINITIONS = {
    "reception": {"role_code": "customer_specialist", "role_name": "客户专员"},
    "layout_assign": {"role_code": "layout_specialist", "role_name": "排版专员"},
    "project_manager": {"role_code": "project_manager", "role_name": "项目经理"},
    "project_specialist": {"role_code": "project_specialist", "role_name": "项目专员"},
    "project_assistant": {"role_code": "project_assistant", "role_name": "项目助理"},
    "review": {"role_code": "reviewer", "role_name": "译审"},
    "special_qc": {"role_code": "project_specialist", "role_name": "项目专员"},
    "layout": {"role_code": "layout_specialist", "role_name": "排版专员"},
    "completed": {"role_code": "completed", "role_name": "-"},
}

ROLE_NAME_BY_CODE = {
    **PROJECT_ROLE_NAME_BY_CODE,
    **{
        definition['role_code']: definition['role_name']
        for definition in STAGE_ROLE_DEFINITIONS.values()
        if definition['role_name'] != '-'
    },
}


def get_stage_role(stage_key: str) -> dict[str, str]:
    """返回阶段对应的稳定角色编码与系统角色名称。"""
    return STAGE_ROLE_DEFINITIONS.get(
        stage_key,
        {"role_code": stage_key or "unknown", "role_name": "-"},
    )
