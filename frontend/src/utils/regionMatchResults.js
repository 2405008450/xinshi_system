import { matchesSearch, matchesSearchFields } from './searchMatching.js'

export const formatRegionMatchRate = value => value == null || !Number.isFinite(Number(value)) ? '-' : `${Number(value).toFixed(2)}%`

// 先筛选和排序全部来源行，再交给视图分页；保留原对象及原始行号。
export function selectRegionMatchResults(rows, columns, { keyword = '', columnFilters = {}, order = 'source' } = {}) {
  const selected = rows.filter(row =>
    matchesSearchFields(columns.map(index => row.values[index]), keyword)
    && columns.every(index => matchesSearch(row.values[index], columnFilters[index] || '')),
  )
  return selected.sort((a, b) => {
    const count = (Number(a.total) || 0) - (Number(b.total) || 0)
    return (order === 'asc' ? count : order === 'desc' ? -count : 0) || a.index - b.index
  })
}
