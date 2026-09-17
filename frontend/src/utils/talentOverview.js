import { TALENT_OVERVIEW_COLUMNS } from '../data/talentOverview.js'

function numericCount(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

export function calculateTalentRowTotal(row, columns = TALENT_OVERVIEW_COLUMNS) {
  return columns.reduce((total, column) => total + numericCount(row?.counts?.[column.key]), 0)
}

export function calculateTalentColumnTotals(rows, columns = TALENT_OVERVIEW_COLUMNS) {
  return Object.fromEntries(columns.map(column => [
    column.key,
    rows.reduce((total, row) => total + numericCount(row?.counts?.[column.key]), 0),
  ]))
}

export function calculateTalentGrandTotal(rows, columns = TALENT_OVERVIEW_COLUMNS) {
  return rows.reduce((total, row) => total + calculateTalentRowTotal(row, columns), 0)
}

export function formatTalentCount(value) {
  return value === null || value === undefined ? '' : Number(value).toLocaleString('zh-CN')
}
