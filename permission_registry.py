"""系统权限点注册表。

权限编码是前后端共同使用的稳定契约；显示名称和分组可以调整，编码一旦使用不应随意修改。
"""

SUPER_ROLE_NAMES = {"admin", "超级管理员"}
ALL_PERMISSION = "*"

PERMISSION_GROUPS = [
    {
        "group": "系统管理",
        "permissions": [
            {"code": "system:users:read", "name": "查看用户"},
            {"code": "system:users:write", "name": "管理用户"},
            {"code": "system:roles:read", "name": "查看角色与权限"},
            {"code": "system:roles:write", "name": "管理角色与权限"},
            {"code": "system:user_roles:write", "name": "分配用户角色"},
        ],
    },
    {
        "group": "项目管理",
        "permissions": [
            {"code": "projects:read", "name": "查看翻译项目"},
            {"code": "projects:write", "name": "管理翻译项目"},
            {"code": "workflow:operate", "name": "执行项目工作流"},
            {"code": "project_files:read", "name": "查看项目文件"},
            {"code": "project_files:write", "name": "管理项目文件"},
        ],
    },
    {
        "group": "客户管理",
        "permissions": [
            {"code": "clients:read", "name": "查看客户"},
            {"code": "clients:write", "name": "管理客户"},
            {"code": "consultations:read", "name": "查看咨询"},
            {"code": "consultations:write", "name": "管理咨询"},
        ],
    },
    {
        "group": "资源与排班",
        "permissions": [
            {"code": "talents:read", "name": "查看人才资源库"},
            {"code": "talents:write", "name": "管理人才资源库"},
            {"code": "recruitment_talents:read", "name": "查看招聘人才敏感信息"},
            {"code": "recruitment_talents:write", "name": "管理招聘人才敏感信息"},
            {"code": "translators:read", "name": "查看译员资源"},
            {"code": "translators:write", "name": "管理译员资源"},
            {"code": "schedule:read", "name": "查看排班"},
            {"code": "schedule:write", "name": "管理排班"},
        ],
    },
    {
        "group": "个人任务与日报",
        "permissions": [
            {"code": "tasks:read", "name": "查看个人任务"},
            {"code": "tasks:self_write", "name": "管理本人任务与工作记录"},
            {"code": "tasks:assign", "name": "向其他用户分配任务"},
            {"code": "reports:read", "name": "查看及确认个人日报"},
            {"code": "reports:export", "name": "导出个人日报"},
        ],
    },
    {
        "group": "财务管理",
        "permissions": [
            {"code": "finance:read", "name": "查看财务"},
            {"code": "finance:write", "name": "管理财务"},
        ],
    },
]

PERMISSION_CODES = {
    permission["code"]
    for group in PERMISSION_GROUPS
    for permission in group["permissions"]
}


def validate_permission_codes(codes: list[str]) -> list[str]:
    """校验、去重并稳定排序权限编码。"""
    normalized = sorted(set(codes))
    invalid = [code for code in normalized if code not in PERMISSION_CODES]
    if invalid:
        raise ValueError(f"未知权限编码：{', '.join(invalid)}")
    return normalized
