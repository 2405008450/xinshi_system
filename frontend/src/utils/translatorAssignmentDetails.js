const readCompatibleField = (item, camelKey, snakeKey) => (
  Object.prototype.hasOwnProperty.call(item, camelKey) ? item[camelKey] : item[snakeKey]
)

export const toNullablePrice = (value) => {
  if (value === null || value === undefined || value === '') return null
  const normalized = Number(value)
  return Number.isFinite(normalized) ? normalized : null
}

export const toDateTimeInputValue = (value) => {
  if (!value) return ''
  const matched = String(value).match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})(?::(\d{2}))?/)
  return matched ? `${matched[1]} ${matched[2]}:${matched[3] || '00'}` : String(value)
}

export const normalizeTranslatorAssignmentDetails = (translators = []) => translators
  .map((item, index) => ({
    arrangementId: item.arrangementId || item.arrangement_id || '',
    translatorName: item.translatorName || item.translator_name || '译员',
    returnTime: toDateTimeInputValue(item.translatorReturnTime || item.translator_return_time),
    completionRemarks: item.completionRemarks || item.completion_remarks || '',
    translatorUnitPrice: toNullablePrice(
      readCompatibleField(item, 'translatorUnitPrice', 'translator_unit_price'),
    ),
    translatorTotalPrice: toNullablePrice(
      readCompatibleField(item, 'translatorTotalPrice', 'translator_total_price'),
    ),
    index,
  }))
  .filter((item) => item.arrangementId)

export const buildTranslatorAssignmentDetailUpdates = (draft = []) => draft.map((item) => ({
  arrangementId: item.arrangementId,
  translatorReturnTime: item.returnTime || null,
  completionRemarks: item.completionRemarks?.trim() || null,
  translatorUnitPrice: toNullablePrice(item.translatorUnitPrice),
  translatorTotalPrice: toNullablePrice(item.translatorTotalPrice),
}))

export const formatTranslatorPrice = (value, precision) => {
  const normalized = toNullablePrice(value)
  if (normalized === null) return '-'
  return `¥${normalized.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: precision,
  })}`
}
