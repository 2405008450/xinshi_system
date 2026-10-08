import { computed, reactive } from 'vue'

const commonColumns = { platform_id: 'platform_name', owner_id: 'owner_name', account_id: 'account_name' }
const emptyFilters = () => ({ range: null, keyword: '', owner_id: '', platform_id: '', account_id: '', state: '' })

// 按日列表与跨日弹窗共用参数构造，筛选状态由各自实例独立保存。
export function useDevelopmentFilters() {
  const filters = reactive(emptyFilters())
  const columnFilters = reactive({})
  const activeColumnKeys = computed(() => Object.keys(columnFilters).filter(key =>
    Array.isArray(columnFilters[key]) ? columnFilters[key].length : Boolean(columnFilters[key]?.trim())))
  const params = () => ({
    start: filters.range?.[0], end: filters.range?.[1],
    ...Object.fromEntries(['keyword', 'owner_id', 'platform_id', 'account_id', 'state']
      .filter(key => filters[key]).map(key => [key, filters[key]])),
    column_filters: activeColumnKeys.value.length
      ? JSON.stringify(Object.fromEntries(activeColumnKeys.value.map(key => [key, columnFilters[key]]))) : undefined,
  })
  function setColumnFilter(key, value) {
    columnFilters[key] = value
    const common = Object.keys(commonColumns).find(name => commonColumns[name] === key)
    if (common) filters[common] = ''
  }
  function clearCommonColumn(key) { delete columnFilters[commonColumns[key]] }
  function resetFilters(state = '') {
    Object.keys(columnFilters).forEach(key => delete columnFilters[key])
    Object.assign(filters, emptyFilters(), { state })
  }
  return { filters, columnFilters, activeColumnKeys, params, setColumnFilter, clearCommonColumn, resetFilters }
}
