"""未成交原因保存在咨询现有 JSONB 中，作为服务端保留的元数据。"""
from pydantic import BaseModel, Field, model_validator

FAILURE_KEY = '_failure_reason'
FAILURE_REASONS = ['价格高', '反应慢', '处理速度不符合客户要求', '无法满足客户要求', '自动放弃', '已找其他公司', '对信实不满意', '一次跟进客户未回应', '多次跟进客户未回应', '自定义添加']
DETAIL_REQUIRED = {'无法满足客户要求', '自动放弃', '对信实不满意', '自定义添加'}


class FailureReasonInput(BaseModel):
    reason: str = Field(min_length=1, max_length=100)
    details: str = Field(default='', max_length=5000)

    @model_validator(mode='after')
    def validate_reason(self):
        self.reason = self.reason.strip()
        self.details = self.details.strip()
        if not self.reason:
            raise ValueError('请选择或填写未成交原因')
        if self.reason in DETAIL_REQUIRED and not self.details:
            raise ValueError('该未成交原因需要补充具体原因或理由')
        return self


def preserve_failure(existing, incoming):
    result = dict(incoming or {})
    result.pop(FAILURE_KEY, None)
    if (existing or {}).get(FAILURE_KEY):
        result[FAILURE_KEY] = existing[FAILURE_KEY]
    return result


def apply_failure(payload, intake, status, existing=None):
    result = preserve_failure(getattr(existing, 'project_intake', None), intake)
    supplied = payload.failure_reason
    if supplied is not None:
        result[FAILURE_KEY] = supplied.model_dump()
    if status == 'failed' and (existing is None or 'status' in payload.model_fields_set or supplied is not None):
        if not result.get(FAILURE_KEY):
            raise ValueError('切换为未成交前，请填写未成交原因')
        FailureReasonInput.model_validate(result[FAILURE_KEY])
    return result
