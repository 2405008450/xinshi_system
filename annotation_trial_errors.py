"""只将已知试标约束转换为业务提示，不向用户暴露数据库异常。"""

from form_errors import field_error

TRIAL_FIELD_PATHS = {
    "轮次": "round_no", "报价金额": "quote_amount", "计费单位": "billing_unit",
    "总体评分": "overall_score", "截止时间": "deadline_at", "人员": "person_id",
    "语言方向": "language_item_id", "平台账号": "platform_account_id", "标注项目": "project_id",
}

TRIAL_CONSTRAINT_ERRORS = {
    "uq_annotation_trial_business_identity": ("相同人员、语言方向、业务类型、职责和轮次已有候选记录，请编辑已有记录或调整轮次", "轮次"),
    "uq_annotation_trial_sequence": ("当前轮次的候选序号已被占用，请关闭后重新打开记录再保存；若仍失败，请联系管理员", "轮次"),
    "ck_annotation_trial_sequence": ("轮次必须为大于 0 的整数", "轮次"),
    "ck_annotation_trial_quote_amount": ("报价金额必须大于 0", "报价金额"),
    "ck_annotation_trial_billing_unit": ("请选择有效的计费单位", "计费单位"),
    "ck_annotation_trial_overall_score": ("总体评分必须为 1～10 的整数", "总体评分"),
    "ck_annotation_trial_time_range": ("截止时间不能早于开始时间", "截止时间"),
    "fk_annotation_trial_person": ("所选人员已不存在，请重新选择人员", "人员"),
    "fk_annotation_trial_language_item": ("所选语言方向已不存在，请重新打开候选记录", "语言方向"),
    "fk_annotation_trial_account": ("所选平台账号已不存在，请清空或重新选择", "平台账号"),
    "fk_annotation_trial_project": ("标注项目已不存在，请刷新项目列表", "标注项目"),
}


def trial_integrity_detail(exc):
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    error = TRIAL_CONSTRAINT_ERRORS.get(constraint)
    if error:
        message, label = error
        return {**field_error(message, TRIAL_FIELD_PATHS[label]), "fieldLabel": label}
    return None
