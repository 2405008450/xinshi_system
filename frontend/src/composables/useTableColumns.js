import { computed, ref, unref, watch } from 'vue'

export function useTableColumns(moduleKey, columns, defaultKeys, options = {}) {
  const resolvedColumns = computed(() => unref(columns) || [])
  const validKeys = computed(() => new Set(resolvedColumns.value.map((column) => column.key)))
  const normalizedDefaults = computed(() => (unref(defaultKeys) || []).filter((key) => validKeys.value.has(key)))
  const normalizedLegacyDefaults = computed(() => (unref(options.legacyDefaultKeys) || []).filter((key) => validKeys.value.has(key)))
  const userKey = localStorage.getItem('user_id') || localStorage.getItem('user_name') || 'anonymous'
  const storageKey = `table-columns:${moduleKey}:${userKey}`

  const readSelection = () => {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return [...normalizedDefaults.value]
    try {
      const parsed = JSON.parse(raw)
      if (!Array.isArray(parsed)) throw new Error('invalid column settings')
      const filtered = parsed.filter((key) => validKeys.value.has(key))
      const isLegacyDefault = normalizedLegacyDefaults.value.length > 0
        && filtered.length === normalizedLegacyDefaults.value.length
        && normalizedLegacyDefaults.value.every((key) => filtered.includes(key))
      if (isLegacyDefault) {
        localStorage.setItem(storageKey, JSON.stringify(normalizedDefaults.value))
        return [...normalizedDefaults.value]
      }
      if (filtered.length !== parsed.length) localStorage.setItem(storageKey, JSON.stringify(filtered))
      return filtered
    } catch {
      localStorage.removeItem(storageKey)
      return [...normalizedDefaults.value]
    }
  }

  const selectedKeys = ref(readSelection())
  watch(selectedKeys, (value) => {
    localStorage.setItem(storageKey, JSON.stringify(value.filter((key) => validKeys.value.has(key))))
  }, { deep: true })

  watch(resolvedColumns, () => {
    const filtered = selectedKeys.value.filter((key) => validKeys.value.has(key))
    if (filtered.length !== selectedKeys.value.length) selectedKeys.value = filtered
  }, { deep: true })

  const isVisible = (key) => selectedKeys.value.includes(key)
  const reset = () => { selectedKeys.value = [...normalizedDefaults.value] }

  return { selectedKeys, isVisible, reset }
}
