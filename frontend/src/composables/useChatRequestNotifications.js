import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { getNotificationPage, getUnreadNotificationCount, markNotificationRead } from '@/api/notifications'
import { subscribe } from '@/utils/realtimeSocket'
import { CONVERSATION_NOTIFICATION_TYPES } from '@/utils/notificationChannels'

const types = CONVERSATION_NOTIFICATION_TYPES
const params = { channel: 'business', notification_types: types }
export function useChatRequestNotifications() {
  const items = ref([]), unread = ref(0), loading = ref(false), error = ref(''), total = ref(0), page = ref(1), pageSize = ref(30)
  const filters = reactive({ keyword: '', notificationType: '', readStatus: 'all' })
  const hasMore = computed(() => page.value * pageSize.value < total.value)
  let sequence = 0, timer, debounceTimer, controller, unsubscribe, unsubscribeSnapshot, disposed = false
  let applied = { keyword: undefined, read_status: 'all' }
  function cancelRequest() { controller?.abort(); sequence++; loading.value = false }
  async function refresh() {
    if (disposed || !localStorage.getItem('token')) return
    controller?.abort(); controller = new AbortController()
    const current = ++sequence
    loading.value = true
    try {
      const [result, count] = await Promise.all([
        getNotificationPage({ ...params, ...applied, skip: (page.value - 1) * pageSize.value, limit: pageSize.value }, { signal: controller.signal }),
        // 导航未读数字始终覆盖整个通知模块，不受搜索条件影响。
        getUnreadNotificationCount(params, { signal: controller.signal }),
      ])
      if (disposed || current !== sequence) return
      const last = Math.max(1, Math.ceil(result.total / pageSize.value))
      if (page.value > last) { page.value = last; return await refresh() }
      items.value = result.items
      total.value = result.total
      unread.value = Number(count?.count || 0)
      error.value = ''
    } catch (e) { if (!disposed && current === sequence && e.code !== 'ERR_CANCELED') error.value = e.detail || e.message || '通知加载失败' }
    finally { if (current === sequence) loading.value = false }
  }
  function query() {
    clearTimeout(debounceTimer); debounceTimer = null
    applied = { keyword: filters.keyword.trim() || undefined, read_status: filters.readStatus,
      notification_type: filters.notificationType || undefined }
    page.value = 1
    return refresh()
  }
  function keywordInput() {
    clearTimeout(debounceTimer); cancelRequest()
    if (!filters.keyword.trim()) return query()
    debounceTimer = setTimeout(() => { debounceTimer = null; void query() }, 400)
  }
  function reset() { Object.assign(filters, { keyword: '', notificationType: '', readStatus: 'all' }); return query() }
  function pageChanged() { if (debounceTimer) return query(); return refresh() }
  function pageSizeChanged() { page.value = 1; return query() }
  const reload = () => { if (!debounceTimer) void refresh() }
  async function read(item) {
    if (!item.is_read) {
      await markNotificationRead(item.id)
      item.is_read = true
      unread.value = Math.max(0, unread.value - 1)
      window.dispatchEvent(new CustomEvent('business-notifications-changed'))
    }
  }
  onMounted(() => {
    reload()
    timer = window.setInterval(reload, 10000)
    unsubscribe = subscribe('notification', payload => { if (types.includes(payload?.notification?.notification_type)) reload() })
    unsubscribeSnapshot = subscribe('snapshot', reload)
    window.addEventListener('business-notifications-changed', reload)
    window.addEventListener('focus', reload)
  })
  onBeforeUnmount(() => {
    disposed = true; cancelRequest(); clearTimeout(debounceTimer); window.clearInterval(timer)
    unsubscribe?.(); unsubscribeSnapshot?.()
    window.removeEventListener('business-notifications-changed', reload)
    window.removeEventListener('focus', reload)
  })
  return { items, unread, loading, error, hasMore, total, page, pageSize, filters, refresh, read, query, keywordInput, reset, pageChanged, pageSizeChanged }
}
