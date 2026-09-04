export const DEFAULT_TRANSLATION_PROJECT_SORT = 'unfinished_first_order_no_desc'

export const TRANSLATION_PROJECT_TIME_SORT_MODES = Object.freeze({
  customerDeadlineTime: 'customer_deadline_time_asc',
  translatorReturnTime: 'translator_return_time_asc',
})

export const getTranslationProjectTimeSortMode = (columnKey) => (
  TRANSLATION_PROJECT_TIME_SORT_MODES[columnKey] || ''
)

export const isTranslationProjectTimeSortActive = (currentMode, columnKey) => (
  currentMode === getTranslationProjectTimeSortMode(columnKey)
)

export const nextTranslationProjectTimeSortMode = (currentMode, columnKey) => {
  const targetMode = getTranslationProjectTimeSortMode(columnKey)
  if (!targetMode) return currentMode
  return currentMode === targetMode ? DEFAULT_TRANSLATION_PROJECT_SORT : targetMode
}

export const getTranslationProjectTimeSortTitle = (currentMode, columnKey, label) => {
  if (isTranslationProjectTimeSortActive(currentMode, columnKey)) {
    return `${label}：恢复默认排序`
  }
  return columnKey === 'translatorReturnTime'
    ? `${label}：待回稿紧急优先`
    : `${label}：待交稿紧急优先`
}
