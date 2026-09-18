export const TRANSLATION_EXPORT_TIME_OPTIONS = Object.freeze([
  { value: 'customer_reception_time', label: '客户接单时间' },
  { value: 'customer_deadline_time', label: '客户交稿时间' },
  { value: 'created_at', label: '创建时间' },
])

export const DEFAULT_TRANSLATION_EXPORT_TIME_FIELD = 'customer_reception_time'

export const TRANSLATION_EXPORT_TYPES = Object.freeze({
  PROJECTS: 'projects',
  RECONCILIATION: 'reconciliation',
  CLIENT_RECONCILIATION: 'client_reconciliation',
  TRANSLATOR_RECONCILIATION: 'translator_reconciliation',
})

const safeParseFilters = (value) => {
  if (!value) return {}
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
  } catch {
    return {}
  }
}

export function buildTranslationExportParams(listParams, exportForm, sort) {
  const [dateStart, dateEnd] = exportForm.dateRange || []
  const filters = safeParseFilters(listParams?.field_filters)
  filters[exportForm.timeField] = {
    op: 'between',
    from: dateStart,
    to: dateEnd,
  }
  return {
    keyword: listParams?.keyword || undefined,
    field_filters: JSON.stringify(filters),
    sort: sort || undefined,
    time_field: exportForm.timeField,
    date_start: dateStart,
    date_end: dateEnd,
  }
}

export function buildTranslationClientReconciliationParams(clientId) {
  return {
    client_id: clientId,
  }
}

export function buildTranslationExportFilename(
  timeField,
  dateRange,
  exportType = TRANSLATION_EXPORT_TYPES.PROJECTS,
  clientLabel = '',
) {
  if (exportType === TRANSLATION_EXPORT_TYPES.CLIENT_RECONCILIATION) {
    const safeClientLabel = String(clientLabel || '客户')
      .trim()
      .replace(/[\\/:*?"<>|]/g, '_')
    return `笔译项目对账单_客户_${safeClientLabel}.xlsx`
  }
  const label = TRANSLATION_EXPORT_TIME_OPTIONS.find((item) => item.value === timeField)?.label || '时间范围'
  const [dateStart, dateEnd] = dateRange || []
  const prefix = {
    [TRANSLATION_EXPORT_TYPES.RECONCILIATION]: '笔译项目对账单',
    [TRANSLATION_EXPORT_TYPES.TRANSLATOR_RECONCILIATION]: '笔译项目译员对账单',
  }[exportType] || '笔译项目导出'
  return `${prefix}_${label}_${dateStart}_至_${dateEnd}.xlsx`
}
