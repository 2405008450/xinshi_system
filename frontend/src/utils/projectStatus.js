const TRANSLATION_STATUS_ALIASES = {
  pending: 'pending_confirmation',
  in_progress: 'confirmed',
  completed: 'sent_to_client',
  terminated: 'cancelled',
}

export const PROJECT_STATUS_OPTIONS = {
  translation: [
    { value: 'pending_confirmation', label: '待确认' },
    { value: 'confirmed', label: '已确认' },
    { value: 'organized', label: '已整理' },
    { value: 'translator_assigned', label: '已排译员' },
    { value: 'sent_to_translator', label: '已发译员' },
    { value: 'translator_returned', label: '译员发回' },
    { value: 'special_checked', label: '已专检' },
    { value: 'typeset', label: '已排版' },
    { value: 'special_checked_typeset', label: '已专检排版' },
    { value: 'reviewed', label: '已审核' },
    { value: 'sent_to_client', label: '已发客户' },
    { value: 'client_feedback', label: '客户反馈' },
    { value: 'feedback_sent_to_client', label: '反馈后发客户' },
    { value: 'cancelled', label: '已取消' },
    { value: 'partially_cancelled', label: '已部分取消' },
    { value: 'paused', label: '已暂停' },
  ],
  interpretation: [
    { value: 'initial_follow_up', label: '初步跟进中' },
    { value: 'in_progress', label: '进行中' },
    { value: 'cancelled', label: '已取消' },
    { value: 'partially_cancelled', label: '已部分取消' },
    { value: 'ended', label: '已结束' },
    { value: 'settled', label: '已结款' },
  ],
  annotation: [
    { value: 'initial_consultation', label: '初步咨询' },
    { value: 'consultation_no_result', label: '初步咨询后无结果' },
    { value: 'resource_sourcing', label: '资源开拓' },
    { value: 'resource_sourcing_cancelled', label: '取消资源开拓' },
    { value: 'trial_preparation', label: '试标准备' },
    { value: 'trial_in_progress', label: '试标中' },
    { value: 'trial_passed', label: '试标通过' },
    { value: 'trial_failed', label: '试标未通过' },
    { value: 'trial_partially_passed', label: '部分试标通过' },
    { value: 'project_in_progress', label: '项目进行中' },
    { value: 'sent_to_client', label: '已发客户' },
    { value: 'client_feedback', label: '客户反馈' },
    { value: 'cancelled', label: '已取消' },
    { value: 'partially_cancelled', label: '已部分取消' },
  ],
  recruitment: [
    { value: 'pending_setup', label: '新建待立项' },
    { value: 'sourcing', label: '立项启动（寻访阶段）' },
    { value: 'recommending', label: '简历推荐中' },
    { value: 'interviewing', label: '面试进行中' },
    { value: 'offer_negotiation', label: 'Offer谈判阶段' },
    { value: 'pending_onboard', label: '候选人待入职' },
    { value: 'probation', label: '已入职保用期' },
    { value: 'closed', label: '项目结案' },
  ],
}

const PROJECT_STATUS_TYPES = {
  pending_confirmation: 'info',
  confirmed: 'primary',
  organized: 'primary',
  translator_assigned: 'warning',
  sent_to_translator: 'warning',
  translator_returned: 'primary',
  special_checked: 'primary',
  typeset: 'primary',
  special_checked_typeset: 'primary',
  reviewed: 'success',
  sent_to_client: 'success',
  client_feedback: 'warning',
  feedback_sent_to_client: 'success',
  cancelled: 'danger',
  partially_cancelled: 'warning',
  paused: 'warning',
  initial_follow_up: 'warning',
  in_progress: 'primary',
  ended: 'success',
  settled: 'success',
  initial_consultation: 'info',
  consultation_no_result: 'info',
  resource_sourcing: 'primary',
  resource_sourcing_cancelled: 'danger',
  trial_preparation: 'warning',
  trial_in_progress: 'warning',
  trial_passed: 'success',
  trial_failed: 'danger',
  trial_partially_passed: 'warning',
  project_in_progress: 'primary',
  pending_setup: 'info',
  sourcing: 'primary',
  recommending: 'warning',
  interviewing: 'warning',
  offer_negotiation: 'warning',
  pending_onboard: 'primary',
  probation: 'success',
  closed: 'success',
}

const LABEL_BY_VALUE = Object.fromEntries(
  Object.values(PROJECT_STATUS_OPTIONS).flat().map((item) => [item.value, item.label])
)

export function resolveProjectType(row) {
  return row?.project_type || 'translation'
}

export function resolveProjectId(row) {
  return row?.project_id || row?.translation_project_id || row?.id || ''
}

export function normalizeProjectStatus(projectType, status) {
  if (!status) return ''
  if ((projectType || 'translation') === 'translation') {
    return TRANSLATION_STATUS_ALIASES[status] || status
  }
  return status
}

export function getProjectStatusOptions(projectType) {
  return PROJECT_STATUS_OPTIONS[projectType] || PROJECT_STATUS_OPTIONS.translation
}

export function getProjectStatusLabel(projectType, status) {
  const normalized = normalizeProjectStatus(projectType, status)
  const typed = getProjectStatusOptions(projectType).find((item) => item.value === normalized)
  return typed?.label || LABEL_BY_VALUE[normalized] || status || '-'
}

export function getProjectStatusType(projectType, status) {
  const normalized = normalizeProjectStatus(projectType, status)
  if ((projectType || 'translation') === 'translation') {
    if (normalized === 'client_feedback') return 'success'
    if (normalized === 'partially_cancelled') return 'danger'
  }
  return PROJECT_STATUS_TYPES[normalized] || 'info'
}

export function isProjectStatusOptionDisabled(projectType, optionValue, currentStatus) {
  const current = normalizeProjectStatus(projectType, currentStatus)
  if (optionValue === current) return true
  if ((projectType || 'translation') === 'translation' && optionValue === 'pending_confirmation') return true
  return false
}
