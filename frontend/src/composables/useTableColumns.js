import { ref, watch } from 'vue'

export function useTableColumns(moduleKey, columns, defaultKeys, options = {}) {
  const validKeys = new Set(columns.map((column) => column.key))
  const normalizedDefaults = defaultKeys.filter((key) => validKeys.has(key))
  const normalizedLegacyDefaults = (options.legacyDefaultKeys || []).filter((key) => validKeys.has(key))
  const userKey = localStorage.getItem('user_id') || localStorage.getItem('user_name') || 'anonymous'
  const storageKey = `table-columns:${moduleKey}:${userKey}`

  const readSelection = () => {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return [...normalizedDefaults]
    try {
      const parsed = JSON.parse(raw)
      if (!Array.isArray(parsed)) throw new Error('invalid column settings')
      const filtered = parsed.filter((key) => validKeys.has(key))
      const isLegacyDefault = normalizedLegacyDefaults.length > 0
        && filtered.length === normalizedLegacyDefaults.length
        && normalizedLegacyDefaults.every((key) => filtered.includes(key))
      if (isLegacyDefault) {
        localStorage.setItem(storageKey, JSON.stringify(normalizedDefaults))
        return [...normalizedDefaults]
      }
      if (filtered.length !== parsed.length) localStorage.setItem(storageKey, JSON.stringify(filtered))
      return filtered
    } catch {
      localStorage.removeItem(storageKey)
      return [...normalizedDefaults]
    }
  }

  const selectedKeys = ref(readSelection())
  watch(selectedKeys, (value) => {
    localStorage.setItem(storageKey, JSON.stringify(value.filter((key) => validKeys.has(key))))
  }, { deep: true })

  const isVisible = (key) => selectedKeys.value.includes(key)
  const reset = () => { selectedKeys.value = [...normalizedDefaults] }

  return { selectedKeys, isVisible, reset }
}
