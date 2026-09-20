function numericCount(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

export const TALENT_OVERVIEW_BLANK_FILTER_VALUE = '__talent_overview_blank__'

export function normalizeTalentOverviewFilterValue(value) {
  return value === null || value === undefined || value === ''
    ? TALENT_OVERVIEW_BLANK_FILTER_VALUE
    : value
}

function matchesTalentOverviewFilter(selectedValues, value) {
  return !Array.isArray(selectedValues)
    || !selectedValues.length
    || selectedValues.includes(normalizeTalentOverviewFilterValue(value))
}

export function filterTalentOverviewRows(rows, columns, filters = {}) {
  const countFilters = filters.counts || {}
  return (rows || []).filter(row => (
    matchesTalentOverviewFilter(filters.language, row.language)
    && matchesTalentOverviewFilter(filters.updatedAt, row.updatedAt)
    && matchesTalentOverviewFilter(filters.rowTotal, calculateTalentRowTotal(row, columns))
    && (columns || []).every(column => (
      matchesTalentOverviewFilter(countFilters[column.key], row?.counts?.[column.key])
    ))
  ))
}

function resolveColumns(rows, columns) {
  if (columns?.length) return columns
  const keys = Object.keys((Array.isArray(rows) ? rows[0] : rows)?.counts || {})
  return keys.map(key => ({ key }))
}

export function calculateTalentRowTotal(row, columns) {
  columns = resolveColumns(row, columns)
  return columns.reduce((total, column) => total + numericCount(row?.counts?.[column.key]), 0)
}

export function calculateTalentColumnTotals(rows, columns) {
  columns = resolveColumns(rows, columns)
  return Object.fromEntries(columns.map(column => [
    column.key,
    rows.reduce((total, row) => total + numericCount(row?.counts?.[column.key]), 0),
  ]))
}

export function calculateTalentGrandTotal(rows, columns) {
  columns = resolveColumns(rows, columns)
  return rows.reduce((total, row) => total + calculateTalentRowTotal(row, columns), 0)
}

export function formatTalentCount(value) {
  return value === null || value === undefined ? '' : Number(value).toLocaleString('zh-CN')
}

export function cloneTalentOverview(columns, rows) {
  return {
    columns: (columns || []).map(column => ({ ...column })),
    rows: (rows || []).map(row => ({
      ...row,
      aliases: [...(row.aliases || [])],
      counts: { ...(row.counts || {}) },
    })),
  }
}

export function appendTalentOverviewColumn(columns, rows, column) {
  const nextColumns = columns.map(item => ({ ...item }))
  const groupIndexes = nextColumns
    .map((item, index) => item.group === column.group ? index : -1)
    .filter(index => index >= 0)
  const insertAt = groupIndexes.length ? groupIndexes[groupIndexes.length - 1] + 1 : nextColumns.length
  nextColumns.splice(insertAt, 0, { ...column })
  return {
    columns: nextColumns,
    rows: rows.map(row => ({ ...row, counts: { ...row.counts, [column.key]: null } })),
  }
}

export function appendTalentOverviewRow(rows, columns, row) {
  return [...rows, {
    ...row,
    counts: Object.fromEntries(columns.map(column => [column.key, null])),
  }]
}
