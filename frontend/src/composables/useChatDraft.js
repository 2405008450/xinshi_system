import {getCurrentInstance,nextTick,onBeforeUnmount,onScopeDispose,ref,watch} from 'vue'
import {chatDraftKey,readChatDraft,writeChatDraft} from '@/utils/chatDrafts'
export function useChatDraft(scope,snapshot,restore){
  const owner=localStorage.getItem('user_id')||'anonymous',error=ref(''),saved=ref(false)
  let key='',restoring=false,timer,disposed=false,version=0,modified=false
  function persist(target=key){clearTimeout(timer);if(!target||restoring||disposed||!modified)return;try{saved.value=writeChatDraft(localStorage,target,snapshot());error.value='';modified=false}catch{error.value='草稿保存失败，请先保留内容再关闭'}}
  watch(scope,async([kind,id])=>{persist();const current=++version;restoring=true;modified=false;key=id?chatDraftKey(owner,kind,id):'';await nextTick();if(disposed||current!==version)return;const data=key?readChatDraft(localStorage,key):null;restore(data||{content:''});saved.value=!!data;restoring=false},{immediate:true,flush:'sync'})
  watch(snapshot,()=>{if(!restoring){modified=true;saved.value=false;clearTimeout(timer);timer=setTimeout(()=>persist(),300)}},{deep:true,flush:'sync'})
  const flush=()=>persist()
  const visibility=()=>{if(document.visibilityState==='hidden')persist()}
  window.addEventListener('beforeunload',flush);document.addEventListener('visibilitychange',visibility)
  if(getCurrentInstance())onBeforeUnmount(()=>{persist();disposed=true;clearTimeout(timer)})
  onScopeDispose(()=>{if(!disposed)persist();disposed=true;version++;clearTimeout(timer);window.removeEventListener('beforeunload',flush);document.removeEventListener('visibilitychange',visibility)})
  return {error,saved,flush,persistNow:()=>{modified=true;persist()}}
}
