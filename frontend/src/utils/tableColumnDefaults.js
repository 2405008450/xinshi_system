export function createTableColumnDefaults({ moduleKey, section = 'main', userKey, storage = globalThis.localStorage }) {
  const key = `table-column-defaults:${encodeURIComponent(moduleKey)}:${encodeURIComponent(section)}:${encodeURIComponent(userKey)}`
  function read() {
    const raw = storage.getItem(key)
    if (raw === null) return null
    try {
      const value = JSON.parse(raw)
      const keys = Array.isArray(value) ? value : value?.keys
      const order = Array.isArray(value) ? null : value?.order
      const valid = items => Array.isArray(items) && items.every(item => typeof item === 'string' || typeof item === 'number')
      if (!valid(keys) || (order !== null && !valid(order))) throw new Error('invalid defaults')
      return { keys: [...new Set(keys)], order }
    } catch {
      storage.removeItem(key)
      return null
    }
  }
  function normalize(keys, columns) {
    const selected = new Set(keys)
    return columns.filter(column => selected.has(column.key)).map(column => column.key)
  }
  return {
    has: () => read() !== null,
    save: (keys, columns, order) => storage.setItem(key, JSON.stringify(order ? { keys: normalize(keys, columns), order } : normalize(keys, columns))),
    restore: columns => {
      const value = read()
      return value === null ? null : normalize(value.keys, columns)
    },
    restoreOrder: () => read()?.order ?? null,
  }
}
