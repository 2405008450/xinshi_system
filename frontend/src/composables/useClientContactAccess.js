import {ref,onMounted,onBeforeUnmount} from 'vue'
import api from '@/api'

export function useClientContactAccess(){
  const canViewClientContacts=ref(false)
  const controller=new AbortController()
  onMounted(async()=>{try{const data=await api.get('/client-contact-people/access',{signal:controller.signal});canViewClientContacts.value=data.can_view_contacts===true}catch{canViewClientContacts.value=false}})
  onBeforeUnmount(()=>controller.abort())
  return {canViewClientContacts}
}
