import { computed, ref, unref, watch } from 'vue'

export function useTableColumns(moduleKey, columns, defaultKeys, options = {}) {
  const resolvedColumns = computed(() => unref(columns) || [])
  const validKeys = computed(() => new Set(resolvedColumns.value.map((column) => column.key)))
  const normalizeKeys = (keys) => {
    const aliases = unref(options.keyAliases) || {}
    const mapped = keys.map((key) => Object.hasOwn(aliases, key) ? aliases[key] : key)
    return [...new Set(mapped)].filter((key) => validKeys.value.has(key))
  }
  const normalizedDefaults = computed(() => normalizeKeys(unref(defaultKeys) || []))
  const normalizedLegacyDefaults = computed(() => {
    const legacyDefaults = unref(options.legacyDefaultKeys) || []
    const legacyGroups = Array.isArray(legacyDefaults[0]) ? legacyDefaults : [legacyDefaults]
    return legacyGroups
      .map(normalizeKeys)
      .filter((keys) => keys.length > 0)
  })
  const userKey = localStorage.getItem('user_id') || localStorage.getItem('user_name') || 'anonymous'
  const storageKey = `table-columns:${moduleKey}:${userKey}`

  const readSelection = () => {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return [...normalizedDefaults.value]
    try {
      const parsed = JSON.parse(raw)
      if (!Array.isArray(parsed)) throw new Error('invalid column settings')
      const filtered = normalizeKeys(parsed)
      const isLegacyDefault = normalizedLegacyDefaults.value.some((legacyKeys) => (
        filtered.length === legacyKeys.length
        && legacyKeys.every((key) => filtered.includes(key))
      ))
      if (isLegacyDefault) {
        localStorage.setItem(storageKey, JSON.stringify(normalizedDefaults.value))
        return [...normalizedDefaults.value]
      }
      if (JSON.stringify(filtered) !== JSON.stringify(parsed)) localStorage.setItem(storageKey, JSON.stringify(filtered))
      return filtered
    } catch {
      localStorage.removeItem(storageKey)
      return [...normalizedDefaults.value]
    }
  }

  const selectedKeys = ref(readSelection())
  watch(selectedKeys, (value) => {
    localStorage.setItem(storageKey, JSON.stringify(normalizeKeys(value)))
  }, { deep: true })

  watch(resolvedColumns, () => {
    const filtered = normalizeKeys(selectedKeys.value)
    if (JSON.stringify(filtered) !== JSON.stringify(selectedKeys.value)) selectedKeys.value = filtered
  }, { deep: true })

  const isVisible = (key) => selectedKeys.value.includes(key)
  const reset = () => { selectedKeys.value = [...normalizedDefaults.value] }

  return { selectedKeys, isVisible, reset }
}
