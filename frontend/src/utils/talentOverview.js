function numericCount(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
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
