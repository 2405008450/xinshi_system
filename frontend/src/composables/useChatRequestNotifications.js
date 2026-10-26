import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getNotifications, getUnreadNotificationCount, markNotificationRead } from '@/api/notifications'
import { subscribe } from '@/utils/realtimeSocket'

const types = ['resource_request_dispatch','chat_summary']
const params = { channel: 'business', notification_types: types }
export function useChatRequestNotifications() {
  const items = ref([]), unread = ref(0), loading = ref(false), error = ref(''), hasMore = ref(false)
  let sequence = 0, timer, unsubscribe, unsubscribeSnapshot, disposed = false
  async function refresh(more = false) {
    if (disposed || !localStorage.getItem('token')) return
    const current = ++sequence
    loading.value = true
    try {
      const skip = more ? items.value.length : 0
      const [rows, count] = await Promise.all([
        getNotifications({ ...params, skip, limit: 30 }), getUnreadNotificationCount(params),
      ])
      if (disposed || current !== sequence) return
      items.value = more ? [...items.value, ...rows.filter(row => !items.value.some(item => item.id === row.id))] : rows
      unread.value = Number(count?.count || 0)
      hasMore.value = rows.length === 30
      error.value = ''
    } catch (e) { if (!disposed && current === sequence) error.value = e.detail || e.message || '通知加载失败' }
    finally { if (current === sequence) loading.value = false }
  }
  const reload = () => refresh()
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
    disposed = true; sequence++; window.clearInterval(timer)
    unsubscribe?.(); unsubscribeSnapshot?.()
    window.removeEventListener('business-notifications-changed', reload)
    window.removeEventListener('focus', reload)
  })
  return { items, unread, loading, error, hasMore, refresh, read }
}
