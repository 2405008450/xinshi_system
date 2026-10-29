// 小型、本机可恢复草稿。只写有变化的数据，不访问业务 API。
export const AUTO_DRAFT_DELAY = 400
export const AUTO_DRAFT_TTL = 7 * 86400000
const SECRET = /password|passwd|passphrase|secret|token|credential|private.?key|api.?key|access.?key|authorization/i
export const draftBusinessNow = (time = Date.now()) => new Date(time + 28800000).toISOString().replace('Z', '+08:00')
export function sanitizeDraft(value, seen = new WeakSet()) {
  if (value == null || ['string', 'number', 'boolean'].includes(typeof value)) return value
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value.toISOString()
  if (typeof value !== 'object' || (typeof Blob !== 'undefined' && value instanceof Blob) || value.nodeType || seen.has(value)) return undefined
  seen.add(value)
  const result = Array.isArray(value) ? value.map(item => sanitizeDraft(item, seen)).filter(item => item !== undefined) : Object.fromEntries(Object.entries(value).filter(([key]) => !SECRET.test(key) && !['__proto__','constructor','prototype'].includes(key)).map(([key, item]) => [key, sanitizeDraft(item, seen)]).filter(([, item]) => item !== undefined))
  seen.delete(value)
  return result
}
export function draftHash(value) {
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  let hash = 2166136261
  for (let i = 0; i < text.length; i++) hash = Math.imul(hash ^ text.charCodeAt(i), 16777619)
  return (hash >>> 0).toString(36)
}
export function createAutoDraftStore({ storage, owner, clock = Date.now, budget = 2 * 1024 * 1024, recordBudget = 256 * 1024 }) {
  const key = `xinshi.autoDraft.v1:${owner}`
  function read() {
    try {
      const records = JSON.parse(storage.getItem(key) || '{}')
      if (!records || typeof records !== 'object' || Array.isArray(records)) return {}
      return Object.fromEntries(Object.entries(records).filter(([, item]) => item && clock() - item.time < AUTO_DRAFT_TTL))
    } catch { return {} }
  }
  function write(records) {
    const ordered = Object.keys(records).sort((a, b) => records[a].time - records[b].time)
    while (ordered.length > 100 || JSON.stringify(records).length * 2 > budget) delete records[ordered.shift()]
    // 配额与聊天等功能共享。写入失败保留现有草稿并向调用方报告，不静默丢失。
    storage.setItem(key, JSON.stringify(records))
  }
  return {
    list: () => Object.values(read()).sort((a, b) => b.time - a.time),
    get: id => read()[id],
    save(record) {
      const data = sanitizeDraft(record.data)
      if (JSON.stringify(data ?? null).length * 2 > recordBudget) throw new Error('此草稿超过256KB，请使用该模块的正式保存或导出功能')
      const records = read(), previous = records[record.id]
      if (previous && JSON.stringify(previous.data) === JSON.stringify(data)) return false
      records[record.id] = { ...record, data, time: clock(), savedAt: draftBusinessNow(clock()) }
      write(records)
      return true
    },
    remove(id) { const records = read(); delete records[id]; write(records) },
  }
}
