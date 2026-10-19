import { formatBusinessDateTimeMinute as formatDateTime } from './dateTime.js'
import { PROJECT_STATUS_OPTIONS } from './projectStatus.js'
export const projectTypeOptions = [
  { value: 'onsite', label: '现场口译' },
  { value: 'booth', label: '展会摊位口译' },
  { value: 'exhibition_escort', label: '展会陪同口译' },
  { value: 'escort', label: '陪同口译' },
  { value: 'small_business_meeting', label: '小型商务会议口译' },
  { value: 'small_non_business_meeting', label: '小型（非商务）会议口译' },
  { value: 'consecutive', label: '会议交传口译' },
  { value: 'simultaneous', label: '会议同传口译' },
  { value: 'online_meeting', label: '线上会议口译' },
  { value: 'online_simultaneous', label: '线上同传口译' },
]
export const ratingOptions = [
  { value: 'very_satisfied', label: '非常满意' },
  { value: 'satisfied', label: '满意' },
  { value: 'basically_satisfied', label: '基本满意' },
  { value: 'dissatisfied', label: '不满意' },
  { value: 'very_dissatisfied', label: '非常不满意' },
]
const projectTypeMap = Object.fromEntries(projectTypeOptions.map(item => [item.value, item.label]))
const ratingMap = Object.fromEntries(ratingOptions.map(item => [item.value, item.label]))
const statusMap = Object.fromEntries(PROJECT_STATUS_OPTIONS.interpretation.map(item => [item.value, item.label]))
export const statusLabel = (value) => statusMap[value] || value || '-'
export const statusType = (value) => ({ initial_follow_up: 'warning', deal_pending_execution: 'primary', in_progress: 'primary', cancelled: 'danger', partially_cancelled: 'warning', ended: 'success', settled: 'success' }[value] || 'info')
export const textValue = (value) => value === null || value === undefined || value === '' ? '-' : String(value)
export const internalRolesText = (row) => {
  const labels = { project_manager: '项目经理', project_specialist: '项目专员', project_assistant: '项目助理' }
  return (row.roleAssignments || []).map((item) => `${labels[item.roleCode] || item.roleName}：${item.assigneeName || '未分配'}`).join('；') || '-'
}
export const arrayText = (value, separator = '；') => Array.isArray(value) && value.length ? value.join(separator) : '-'
export const formatRange = (item) => {
  const scheduled = `${formatDateTime(item.scheduledStart)} 至 ${formatDateTime(item.scheduledEnd)}`
  const actual = item.actualStart || item.actualEnd ? `；实际 ${formatDateTime(item.actualStart)} 至 ${formatDateTime(item.actualEnd)}` : ''
  return `${scheduled}${actual}`
}
export const timeRangesText = (items) => Array.isArray(items) && items.length ? items.map(formatRange).join('；') : '-'
export const projectTypesText = (row) => Array.isArray(row.projectTypes) && row.projectTypes.length ? row.projectTypes.map((value) => projectTypeMap[value] || value).join('；') : '-'
export const ratingText = (rating, note) => [ratingMap[rating] || rating, note].filter(Boolean).join('：') || '-'
export const interpreterRatingsText = (items) => Array.isArray(items) && items.length
  ? items.map((item) => `${item.translatorName}：${ratingText(item.customerRating, item.evaluationNote)}`).join('；')
  : '-'
