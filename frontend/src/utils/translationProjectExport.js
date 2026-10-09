import { buildProjectExportParams, buildClientReconciliationParams } from './projectExport.js'

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

// 保留现有笔译调用接口和文件名规则。
export const buildTranslationExportParams = buildProjectExportParams
export const buildTranslationClientReconciliationParams = buildClientReconciliationParams

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
