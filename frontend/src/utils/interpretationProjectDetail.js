import { formatBusinessDateTimeMinute as formatDateTime } from './dateTime.js'
import { PROJECT_STATUS_OPTIONS } from './projectStatus.js'
export const projectTypeOptions = [
  { value: 'onsite', label: '现场口译' },
  { value: 'booth', label: '展会摊位口译' },
  { value: 'exhibition_escort', label: '展会陪同口译' },
  { value: 'tourism_escort', label: '旅游陪同口译' },
  { value: 'business_escort', label: '商务陪同口译' },
  { value: 'other_escort', label: '其他陪同口译' },
  { value: 'small_business_meeting', label: '小型商务会议口译' },
  { value: 'small_non_business_meeting', label: '小型（非商务）会议口译' },
  { value: 'consecutive', label: '会议交传口译' },
  { value: 'simultaneous', label: '会议同传口译' },
  { value: 'online_meeting', label: '线上会议口译' },
  { value: 'online_simultaneous', label: '线上同传口译' },
]
export const projectTypeDescriptions = {
  onsite: '现场口译的通用类别，适用于现场接待、访问等尚未归入下列具体场景的口译；已有明确场景时优先选择具体类型。',
  booth: '译员主要在固定展位接待来访者，协助产品介绍、询价及洽谈。',
  exhibition_escort: '译员随客户走访展馆或多个展位，协助观展、交流及现场洽谈。',
  tourism_escort: '围绕游览、交通、住宿、餐饮等旅游行程提供随行语言协助。',
  business_escort: '围绕商务拜访、工厂考察、采购及商务洽谈提供随行口译。',
  other_escort: '旅游、商务及展会以外的陪同场景，例如就医、办事或生活事务陪同；请在具体任务中写明用途。',
  small_business_meeting: '小范围商务会议或谈判，以双方轮流交流、分段翻译为主。',
  small_non_business_meeting: '小范围非商务交流，例如学术讨论、文化交流或内部沟通，以轮流交流为主。',
  consecutive: '正式会议中的交替传译：发言人讲完一段后暂停，译员再翻译，需为翻译预留时间。',
  simultaneous: '现场会议中的同声传译：译员与发言人近乎同步工作，通常需要同传设备，并按时长安排轮换。',
  online_meeting: '通过线上会议平台提供口译，通常由发言人与译员轮流讲话；需提前确认平台及音视频条件。',
  online_simultaneous: '通过线上平台近乎同步传译，需确认平台同传频道、音频条件及译员轮换。',
}
export const ratingOptions = [
  { value: 'very_satisfied', label: '非常满意' },
  { value: 'satisfied', label: '满意' },
  { value: 'basically_satisfied', label: '基本满意' },
  { value: 'dissatisfied', label: '不满意' },
  { value: 'very_dissatisfied', label: '非常不满意' },
]
const projectTypeMap = { escort: '陪同口译', ...Object.fromEntries(projectTypeOptions.map(item => [item.value, item.label])) }
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
