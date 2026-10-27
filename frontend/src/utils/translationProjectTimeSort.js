import { parseBusinessDateTime } from './deadlineDisplay.js'

export const DEFAULT_TRANSLATION_PROJECT_SORT = 'order_no_desc'

export const TRANSLATION_PROJECT_TIME_SORT_MODES = Object.freeze({
  customerDeadlineTime: 'customer_deadline_time_asc',
  translatorReturnTime: 'translator_return_time_asc',
  assignedTranslators: 'assigned_translator_name_asc',
})

export const getTranslationProjectTimeSortMode = (columnKey) => (
  TRANSLATION_PROJECT_TIME_SORT_MODES[columnKey] || ''
)

export const getTranslationProjectSortDirection = (currentMode,columnKey) => {
  const mode=getTranslationProjectTimeSortMode(columnKey)
  if(!mode)return 'none'
  return currentMode===mode?'ascending':currentMode===mode.replace(/_asc$/,'_desc')?'descending':'none'
}
export const isTranslationProjectTimeSortActive = (currentMode, columnKey) => getTranslationProjectSortDirection(currentMode,columnKey)!=='none'

export const nextTranslationProjectTimeSortMode = (currentMode, columnKey) => {
  const targetMode = getTranslationProjectTimeSortMode(columnKey)
  if (!targetMode) return currentMode
  if(currentMode===targetMode)return targetMode.replace(/_asc$/,'_desc')
  return currentMode===targetMode.replace(/_asc$/,'_desc')?DEFAULT_TRANSLATION_PROJECT_SORT:targetMode
}

export const getTranslationProjectTimeSortTitle = (currentMode, columnKey, label) => {
  const direction=getTranslationProjectSortDirection(currentMode,columnKey)
  const unit=columnKey==='assignedTranslators'?'姓名首字母':'时间'
  if(direction==='ascending')return `${label}：当前${unit}升序，点击切换降序`
  if(direction==='descending')return `${label}：当前${unit}降序，点击取消排序`
  return `${label}：不排序，点击按${unit}升序`
}

export const getTranslationSubOrderEarliestReturnTime = (subOrder) => {
  const timestamps = (Array.isArray(subOrder?.assignedTranslators)
    ? subOrder.assignedTranslators
    : [])
    .map((item) => item?.translatorReturnTime || item?.translator_return_time || '')
    .map((value) => parseBusinessDateTime(value)?.getTime())
    .filter(Number.isFinite)

  return timestamps.length ? Math.min(...timestamps) : Number.POSITIVE_INFINITY
}

export const hasTranslationSubOrderReturnTime = (subOrder) => (
  Number.isFinite(getTranslationSubOrderEarliestReturnTime(subOrder))
)
