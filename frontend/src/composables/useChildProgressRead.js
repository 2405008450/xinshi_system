import {computed,ref,onMounted,onBeforeUnmount} from 'vue'
import {childProgressReadStorageKey,parseChildProgressRead,childProgressReadCount,markChildProgressRead} from '@/utils/childProgressRead'
const epoch=ref(0)
export function useChildProgressRead(projectId,keys){
  const storageKey=()=>childProgressReadStorageKey(localStorage.getItem('user_id')||'anonymous',projectId())
  function read(){try{return parseChildProgressRead(localStorage.getItem(storageKey()))}catch{return []}}
  const count=computed(()=>{void epoch.value;return childProgressReadCount(keys(),read())})
  function mark(key){if(!keys().includes(key))return;try{localStorage.setItem(storageKey(),JSON.stringify(markChildProgressRead(keys(),read(),key)));epoch.value++}catch{}}
  function changed(event){if(event.key===storageKey()||event.key===null)epoch.value++}
  onMounted(()=>window.addEventListener('storage',changed));onBeforeUnmount(()=>window.removeEventListener('storage',changed))
  return {count,mark}
}
