const empty = value => value == null || value === ''

export { customFieldRules } from './annotationCustomFieldRules.js'

// Pydantic Decimal 响应为字符串；只在数字控件入口转换，不能全局转换空值。
export function trialFormValues(row = {}) {
  return { ...row, quoteAmount: empty(row.quoteAmount) ? null : Number(row.quoteAmount), customValues: { ...(row.customValues || {}) } }
}

export const conversionPercent = rate => Number((Number(rate ?? 0.1) * 100).toFixed(2))
export const conversionRate = percent => Number((Number(percent) / 100).toFixed(4))

// 可清空的下拉框会产生空字符串，接口的可选枚举和 UUID 使用 null。
export function trialPayload(form) {
  const { id, sequenceNo, ...payload } = form
  for (const key of ['platformAccountId', 'willingnessLevel', 'quoteCurrency', 'billingUnit', 'trialResult', 'cooperationLevel', 'punctualityLevel', 'startedAt', 'deadlineAt', 'submittedAt']) {
    if (empty(payload[key])) payload[key] = null
  }
  return payload
}

export function trialRules(form) {
  const required = message => ({ required: true, message, trigger: ['change', 'blur'] })
  const check = (validate, message) => ({
    validator: (_rule, value, callback) => validate(value) ? callback() : callback(new Error(message)),
    trigger: ['change', 'blur'],
  })
  return {
    projectId: [required('请选择标注项目')],
    languageItemId: [required('请选择语言方向')],
    personId: [required('请选择人员')],
    activityType: [required('请选择业务类型')],
    dutyRole: [required('请选择工作职责')],
    candidateStage: [required('请选择候选阶段')],
    roundNo: [required('请填写轮次'), check(value => Number.isInteger(value) && value > 0, '轮次必须为大于 0 的整数')],
    quoteAmount: [
      ...(form.billingUnit ? [required('填写计费单位后，请填写报价金额')] : []),
      check(value => empty(value) || (Number.isFinite(value) && value > 0), '报价金额必须大于 0'),
    ],
    billingUnit: empty(form.quoteAmount) ? [] : [required('填写报价金额后，请选择计费单位')],
    deadlineAt: [check(value => !value || !form.startedAt || new Date(value) >= new Date(form.startedAt), '截止时间不能早于开始时间')],
    resultNote: form.trialResult === 'partially_passed'
      ? [{ ...required('部分通过时请填写结果说明'), whitespace: true }] : [],
    overallScore: [check(value => empty(value) || (Number.isInteger(value) && value >= 1 && value <= 10), '总体评分必须为 1～10 的整数')],
  }
}
