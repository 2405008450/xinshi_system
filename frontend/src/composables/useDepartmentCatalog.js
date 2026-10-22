import { onMounted, onBeforeUnmount } from 'vue'
import api from '@/api'
import { applyDepartmentCatalog } from '@/constants/departments'
import { subscribe } from '@/utils/realtimeSocket'

let pending
export async function refreshDepartments() {
  if (pending) return pending
  pending=api.get('/departments').then(data=>{applyDepartmentCatalog(data);return data}).finally(()=>{pending=null})
  return pending
}
export function useDepartmentCatalog() {
  let timer,unsubscribe
  const refresh=()=>{void refreshDepartments().catch(()=>{})}
  onMounted(()=>{refresh();timer=setInterval(refresh,30000);window.addEventListener('focus',refresh);unsubscribe=subscribe('departments_changed',refresh)})
  onBeforeUnmount(()=>{clearInterval(timer);window.removeEventListener('focus',refresh);unsubscribe?.()})
}
