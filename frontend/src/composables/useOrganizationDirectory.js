import { ref, onMounted, onBeforeUnmount } from 'vue'
import api from '@/api'
import { subscribe } from '@/utils/realtimeSocket'

export function useOrganizationDirectory() {
  const people=ref([])
  let controller,sequence=0,unsubscribe
  const refresh=async()=>{
    const seq=++sequence;controller?.abort();controller=new AbortController()
    try {const data=await api.get('/departments/organization',{signal:controller.signal});if(seq===sequence)people.value=data.people}
    catch { /* 主部门在接口失败时仍可见，表单操作不依赖此展示请求。 */ }
  }
  onMounted(()=>{refresh();unsubscribe=subscribe('departments_changed',refresh)})
  onBeforeUnmount(()=>{sequence++;controller?.abort();unsubscribe?.()})
  return {people,refresh}
}
