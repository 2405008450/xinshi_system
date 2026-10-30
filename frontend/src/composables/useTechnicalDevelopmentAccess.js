import { onMounted, onBeforeUnmount } from 'vue'
import api from '@/api'
import { subscribe } from '@/utils/realtimeSocket'
import { technicalDevelopmentAccess } from '@/utils/technicalDevelopmentAccess'
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
  let timer, unsubscribe
  const refresh = () => { void refreshTechnicalDevelopmentAccess().catch(() => {}) }
  onMounted(() => { refresh(); timer = setInterval(refresh, 30000); window.addEventListener('focus', refresh); unsubscribe = subscribe('departments_changed', refresh) })
  onBeforeUnmount(() => { clearInterval(timer); window.removeEventListener('focus', refresh); unsubscribe?.() })
}
