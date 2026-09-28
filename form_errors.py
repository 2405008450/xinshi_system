"""安全的表单错误协议：仅映射明确已知的数据库约束。"""


def field_error(message: str, path=None) -> dict:
    return {"message": message, "fieldErrors": [{"path": path, "message": message}] if path else []}


CONSTRAINT_FIELDS = {
    "client_client_code_key": ("客户编号已存在，请使用其他编号", "client_code"),
    "sub_client_code_key": ("子客户编号已存在，请使用其他编号", "sub_client_code"),
    "translation_project_order_no_key": ("项目订单号已存在，请刷新后重试", "order_no"),
    "translation_sub_order_no_key": ("子订单号已存在，请使用其他编号", "sub_order_no"),
    "app_user_username_key": ("登录账号已存在，请使用其他账号", "username"),
    "role_role_name_key": ("角色名称已存在，请使用其他名称", "role_name"),
    "uq_recruitment_project_order_no": ("项目订单号已存在，请刷新后重试", "order_no"),
    "ck_recruitment_headcount_range": ("招聘人数上限不能小于下限", "headcount_max"),
    "ck_recruitment_employment_range": ("用工结束时间不能早于开始时间", "employment_end"),
    "ck_recruitment_service_fee_rate": ("服务费比例必须在 0～100 之间", "service_fee_rate"),
    "fk_recruitment_project_client": ("所选客户已不存在，请重新选择", "client_id"),
    "fk_recruitment_candidate_person": ("所选人才已不存在，请重新选择", "person_id"),
    "ck_resource_request_progress": ("完成进度必须在 0～100 之间", "progress_percent"),
    "fk_resource_request_client": ("所选客户已不存在，请重新选择", "client_id"),
}


def integrity_error_detail(exc, fallback: str):
    """禁止从异常字符串提取或回传 SQL、参数、账号等敏感内容。"""
    constraint = getattr(getattr(getattr(exc, "orig", None), "diag", None), "constraint_name", None)
    known = CONSTRAINT_FIELDS.get(constraint)
    return field_error(*known) if known else fallback
