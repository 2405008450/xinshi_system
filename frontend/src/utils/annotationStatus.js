// 同时兼容接口枚举和旧缓存的驼峰键，界面不直接暴露英文状态代码。
export const annotationStatusLabels = {
  initial_consultation: '初步咨询', consultation_no_result: '初步咨询后无结果',
  resource_sourcing: '资源开拓', resource_sourcing_cancelled: '取消资源开拓',
  trial_preparation: '试标准备', trial_in_progress: '试标中', trial_submitted: '试标已提交',
  trial_passed: '试标通过', trial_failed: '试标未通过', trial_partially_passed: '部分试标通过',
  project_in_progress: '项目进行中', sent_to_client: '已发客户', client_feedback: '客户反馈',
  cancelled: '已取消', partially_cancelled: '已部分取消', paused: '暂停',
  actively_abandoned: '主动放弃', ended: '已结束',
}
const types = { resource_sourcing: 'primary', resource_sourcing_cancelled: 'danger',
  trial_preparation: 'warning', trial_in_progress: 'warning', trial_submitted: 'primary',
  trial_passed: 'success', trial_failed: 'danger', trial_partially_passed: 'warning',
  project_in_progress: 'primary', sent_to_client: 'success', client_feedback: 'warning',
  cancelled: 'danger', partially_cancelled: 'warning', paused: 'warning',
  actively_abandoned: 'danger', ended: 'success' }
export const normalizeAnnotationStatus = value => String(value || '').replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
export const annotationStatusLabel = value => annotationStatusLabels[normalizeAnnotationStatus(value)] || (value ? '未知状态' : '-')
export const annotationStatusType = value => types[normalizeAnnotationStatus(value)] || 'info'
export const annotationStatusSummary = counts => {
  const merged = new Map()
  for (const [key, count] of Object.entries(counts || {})) {
    const status = normalizeAnnotationStatus(key)
    merged.set(status, (merged.get(status) || 0) + Number(count || 0))
  }
  return [...merged].filter(([, count]) => count > 0).map(([status, count]) => ({ status, count, label: annotationStatusLabel(status) }))
}

export const convertAnnotationKeys = (value, converter) => {
  if (Array.isArray(value)) return value.map(item => convertAnnotationKeys(item, converter))
  if (value && value.constructor === Object) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [converter(key),
      ['child_status_counts', 'childStatusCounts'].includes(key) ? item : convertAnnotationKeys(item, converter)]))
  }
  return value
}
