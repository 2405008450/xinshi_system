export function workflowFormValues(row = {}) {
  const number = value => value == null || value === '' ? null : Number(value)
  return { ...row, audioDurationValue: number(row.audioDurationValue), amount: number(row.amount), customValues: { ...(row.customValues || {}) } }
}

export function workflowRules(form) {
  const required = message => ({ required: true, message, trigger: 'change' })
  const pair = (unit, label, minimum) => ({
    required: Boolean(unit),
    validator: (_rule, value, callback) => {
      if ((value == null) !== !unit) return callback(new Error(`${label}和单位必须同时填写`))
      if (value != null && (!Number.isFinite(value) || (minimum === 0 ? value < 0 : value <= 0))) {
        return callback(new Error(`${label}必须${minimum === 0 ? '大于等于' : '大于'} 0`))
      }
      callback()
    }, trigger: ['change', 'blur'],
  })
  return {
    projectId: [required('请选择标注项目')],
    personId: [required('请选择人员')],
    assignmentRole: [required('请选择人员角色')],
    audioDurationValue: [pair(form.audioDurationUnit, '音频长度', 0)],
    amount: [pair(form.unit, '人员价格', 1)],
  }
}
