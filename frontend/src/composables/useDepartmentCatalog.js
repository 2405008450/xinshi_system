import { onMounted, onBeforeUnmount } from 'vue'
import api from '@/api'
import { applyDepartmentCatalog } from '@/constants/departments'
import { subscribe } from '@/utils/realtimeSocket'
import { createVisiblePolling } from '@/utils/visiblePolling'

let pending
export async function refreshDepartments() {
  if (pending) return pending
  pending=api.get('/departments').then(data=>{applyDepartmentCatalog(data);return data}).finally(()=>{pending=null})
  return pending
}
export function useDepartmentCatalog() {
  let unsubscribe
  // 部门变更由 departments_changed 推送；轮询只兜底跨后端推送不可达的情况，隐藏页面不轮询。
  const polling=createVisiblePolling({task:()=>refreshDepartments().catch(()=>{}),visibleMs:5*60*1000,hiddenMs:null})
  const onFocus=()=>{void polling.trigger(false)}
  onMounted(()=>{polling.start({immediate:true});window.addEventListener('focus',onFocus);unsubscribe=subscribe('departments_changed',()=>{void polling.trigger(true)})})
  onBeforeUnmount(()=>{polling.stop();window.removeEventListener('focus',onFocus);unsubscribe?.()})
}
