export function normalizeColumnOrder(keys, columns) {
  const valid = new Set(columns.map(column => column.key))
  return [...new Set([...(Array.isArray(keys) ? keys : []), ...valid])].filter(key => valid.has(key))
}

export function moveColumn(keys, from, to) {
  const result = [...keys]
  const start = result.indexOf(from), end = result.indexOf(to)
  if (start < 0 || end < 0 || start === end) return result
  result.splice(start, 1)
  result.splice(end, 0, from)
  return result
}

export function sortColumns(columns, order) {
  const rank = new Map(order.map((key, index) => [key, index]))
  return [...columns].sort((a, b) => (rank.get(a.key) ?? Infinity) - (rank.get(b.key) ?? Infinity))
}
