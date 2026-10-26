import { reactive } from 'vue'
import { annotationChatRequest } from '@/api/projectChat'

const statuses = reactive({})
const pending = new Set()
let timer
export function useAnnotationConversationStatus() {
  function refresh(id) {
    if (!id) return
    pending.add(id)
    clearTimeout(timer)
    timer = setTimeout(async () => {
      const ids = [...pending]; pending.clear()
      for (let offset=0;offset<ids.length;offset+=100) {
        const batch=ids.slice(offset,offset+100)
        try {
          const result=await annotationChatRequest('', 'conversation-status', {method:'post',data:{projectIds:batch}})
          result.items.forEach(row=>{statuses[row.projectId]={...row,error:''}})
        } catch(e) { batch.forEach(id=>{statuses[id]={error:e.detail || '会话状态加载失败'}}) }
      }
    }, 0)
  }
  return { statuses, refresh }
}
