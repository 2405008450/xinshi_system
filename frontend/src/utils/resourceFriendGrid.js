// 后端按账号存储，录入时按语种合并；保留空白与明确零。
export function friendRowsToGrid(rows) {
  const groups = new Map()
  for (const row of rows) {
    const key = `${row.language_value}|${row.overview_key}`
    if (!groups.has(key)) groups.set(key, { language_value: row.language_value, language_type: row.language_type, overview_key: row.overview_key, cells: {}, channels: {} })
    const group = groups.get(key)
    group.cells[row.column_key] = row.count
    group.channels[row.column_key] = row.channel
  }
  return [...groups.values()]
}
export function friendGridToRows(rows, accounts) {
  return rows.flatMap(row => (Object.keys(row.cells).length ? Object.entries(row.cells) : row.language_value && accounts.length ? [[accounts[0].key, null]] : []).map(([key, count]) => ({
    language_value: row.language_value, language_type: row.language_type, overview_key: row.overview_key,
    column_key: key, channel: accounts.find(a => a.key === key)?.channel || row.channels[key], count: count ?? null,
  })))
}
export const friendCount = value => Number.isInteger(value) && value >= 0 ? value : 0
export const parseFriendCount = value => value.trim() === '' ? null : /^\d+$/.test(value.trim()) ? Number(value.trim()) : value
export function parseFriendPaste(text) {
  const cells = text.replace(/\r\n?/g, '\n').replace(/\n+$/, '').split('\n').map(line => line.split('\t').map(parseFriendCount))
  if (cells.some(row => row.some(value => value !== null && (!Number.isInteger(value) || value < 0 || value > 1000000)))) throw new Error('只能粘贴 0～1000000 的整数或空白，请勿包含表头和小计。')
  return cells
}
