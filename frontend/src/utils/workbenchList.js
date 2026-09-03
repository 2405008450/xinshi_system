export const WORKBENCH_PAGE_SIZE_OPTIONS = Object.freeze([10, 20, 50])

export function paginateWorkbenchRows(rows, page = 1, pageSize = 10) {
  const safeRows = Array.isArray(rows) ? rows : []
  const safePageSize = WORKBENCH_PAGE_SIZE_OPTIONS.includes(pageSize) ? pageSize : 10
  const safePage = Math.max(1, Number(page) || 1)
  const start = (safePage - 1) * safePageSize
  return safeRows.slice(start, start + safePageSize)
}

export function getWorkbenchLastPage(total, pageSize = 10) {
  const safePageSize = WORKBENCH_PAGE_SIZE_OPTIONS.includes(pageSize) ? pageSize : 10
  return Math.max(1, Math.ceil(Math.max(0, Number(total) || 0) / safePageSize))
}

export function workbenchFieldsInclude(row, fields, keyword) {
  const normalized = String(keyword || '').trim().toLocaleLowerCase('zh-CN')
  if (!normalized) return true
  return fields.some(field => String(row?.[field] || '').toLocaleLowerCase('zh-CN').includes(normalized))
}

export function countActiveWorkbenchFilterGroups(model, keys) {
  return keys.reduce((count, key) => {
    const value = model?.[key]
    const active = Array.isArray(value) ? value.length > 0 : Boolean(String(value || '').trim())
    return count + Number(active)
  }, 0)
}

export function getWorkbenchFilterStorageKey(scope, userId, userName = '') {
  const owner = String(userId || userName || 'anonymous').trim() || 'anonymous'
  return `workbench-filters:${scope}:${owner}`
}

export function clearWorkbenchFilterKeys(model, keys) {
  for (const key of keys) {
    model[key] = Array.isArray(model[key]) ? [] : ''
  }
  return model
}

/**
 * 常用文本条件按字段组 AND，多选条件在同一字段内 OR、字段组之间 AND。
 */
export function matchesWorkbenchFilterGroups(row, filters, config = {}) {
  for (const [filterKey, fields] of Object.entries(config.textFields || {})) {
    if (!workbenchFieldsInclude(row, fields, filters?.[filterKey])) return false
  }
  for (const [filterKey, getRowValues] of Object.entries(config.multiValueGetters || {})) {
    const selected = Array.isArray(filters?.[filterKey]) ? filters[filterKey] : []
    if (!selected.length) continue
    const rawValues = getRowValues(row)
    const rowValues = Array.isArray(rawValues) ? rawValues : [rawValues]
    if (!selected.some(value => rowValues.includes(value))) return false
  }
  return true
}
