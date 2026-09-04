export const TRANSLATION_EXPORT_TIME_OPTIONS = Object.freeze([
  { value: 'customer_reception_time', label: '客户接单时间' },
  { value: 'customer_deadline_time', label: '客户交稿时间' },
  { value: 'created_at', label: '创建时间' },
])

export const DEFAULT_TRANSLATION_EXPORT_TIME_FIELD = 'customer_reception_time'

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

export function buildTranslationExportFilename(timeField, dateRange) {
  const label = TRANSLATION_EXPORT_TIME_OPTIONS.find((item) => item.value === timeField)?.label || '时间范围'
  const [dateStart, dateEnd] = dateRange || []
  return `笔译项目导出_${label}_${dateStart}_至_${dateEnd}.xlsx`
}
