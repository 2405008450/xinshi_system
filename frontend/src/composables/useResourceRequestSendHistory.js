import { onBeforeUnmount,onMounted,ref,watch } from 'vue'
import {subscribe} from '@/utils/realtimeSocket'
import { getResourceRequestSendHistory } from '@/api/resourceRequests'
export function useResourceRequestSendHistory(requestId) {
  const records = ref({circle:[],post:[],development:[]}), loading=ref(false), error=ref('')
  let sequence=0, controller
  async function refresh() {
    controller?.abort(); controller=new AbortController(); const current=++sequence, id=requestId()
    if (!id) {records.value={circle:[],post:[],development:[]};loading.value=false;error.value='';return}
    loading.value=true;error.value=''
    try {const result=await getResourceRequestSendHistory(id,{signal:controller.signal});if(current===sequence)records.value=result.records}
    catch(e){if(current===sequence && e.code!=='ERR_CANCELED')error.value=e.detail||e.message||'发送记录加载失败'}
    finally{if(current===sequence)loading.value=false}
  }
  watch(requestId,()=>{records.value={circle:[],post:[],development:[]};refresh()},{immediate:true})
  let unsubscribe
  onMounted(()=>{unsubscribe=subscribe('notification',payload=>{const notice=payload?.notification;if(notice?.notification_type==='resource_request_dispatch' && Object.values(records.value).flat().some(item=>item.id===notice.related_entity_id))refresh()})})
  onBeforeUnmount(()=>{sequence++;controller?.abort();unsubscribe?.()})
  return {records,loading,error,refresh}
}
