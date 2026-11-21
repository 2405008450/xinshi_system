import { onMounted, onBeforeUnmount } from 'vue'
import api from '@/api'
import { subscribe } from '@/utils/realtimeSocket'
import { technicalDevelopmentAccess } from '@/utils/technicalDevelopmentAccess'
import { createVisiblePolling } from '@/utils/visiblePolling'
let pending, pendingUser
export async function refreshTechnicalDevelopmentAccess() {
  const userId = localStorage.getItem('user_id') || ''
  if (pending && pendingUser === userId) return pending
  pendingUser = userId
  const request = api.get('/technical-development/access').then(result => { if ((localStorage.getItem('user_id') || '') === userId) Object.assign(technicalDevelopmentAccess, { userId, can_enter: result.can_enter === true }); return result })
  pending = request
  try { return await request } catch (e) { if ((localStorage.getItem('user_id') || '') === userId) Object.assign(technicalDevelopmentAccess, { userId, can_enter: false }); throw e }
  finally { if (pending === request) pending = null }
}
export function useTechnicalDevelopmentAccess() {
  let unsubscribe
  // 权限变化由 departments_changed 推送；轮询只兜底跨后端推送不可达的情况，隐藏页面不轮询。
  const polling = createVisiblePolling({ task: () => refreshTechnicalDevelopmentAccess().catch(() => {}), visibleMs: 5 * 60 * 1000, hiddenMs: null })
  const onFocus = () => { void polling.trigger(false) }
  onMounted(() => { polling.start({ immediate: true }); window.addEventListener('focus', onFocus); unsubscribe = subscribe('departments_changed', () => { void polling.trigger(true) }) })
  onBeforeUnmount(() => { polling.stop(); window.removeEventListener('focus', onFocus); unsubscribe?.() })
}
