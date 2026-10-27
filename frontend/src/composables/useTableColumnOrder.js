import { computed, ref, unref, watch } from 'vue'
import { normalizeColumnOrder, sortColumns } from '../utils/tableColumnOrder.js'

const entries = new Map()
function entry(moduleKey, section) {
  const user = localStorage.getItem('user_id') || localStorage.getItem('user_name') || 'anonymous'
  const key = `table-column-order:${encodeURIComponent(moduleKey)}:${section}:${encodeURIComponent(user)}`
  if (!entries.has(key)) {
    let saved = null
    try {
      const raw = localStorage.getItem(key)
      if (raw !== null) {
        saved = JSON.parse(raw)
        if (!Array.isArray(saved) || !saved.every(item => typeof item === 'string' || typeof item === 'number')) throw Error('invalid order')
      }
    } catch { localStorage.removeItem(key); saved = null }
    entries.set(key, { saved: ref(saved), columns: ref([]), key })
  }
  return entries.get(key)
}

export function useTableColumnOrder(moduleKey, section = 'main', columns) {
  const state = computed(() => entry(unref(moduleKey), unref(section)))
  if (columns) watch([() => state.value.key, () => unref(columns)], ([, fields]) => { state.value.columns.value = fields || [] }, { immediate: true, deep: true })
  const order = computed(() => normalizeColumnOrder(state.value.saved.value, state.value.columns.value))
  const orderedColumns = computed(() => sortColumns(state.value.columns.value, order.value))
  function setOrder(keys) {
    const value = normalizeColumnOrder(keys, state.value.columns.value)
    localStorage.setItem(state.value.key, JSON.stringify(value))
    state.value.saved.value = value
  }
  function resetOrder() {
    localStorage.removeItem(state.value.key)
    state.value.saved.value = null
  }
  return { order, orderedColumns, setOrder, resetOrder, custom: computed(() => state.value.saved.value !== null), columns: computed(() => state.value.columns.value) }
}
