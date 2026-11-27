import {ref} from 'vue'
import {annotationChatRequest,chatRequest} from '@/api/projectChat'
import {useAnnotationFollowed} from './useAnnotationFollowed'
export function useChatFavorites(){
 const {sessions,refresh}=useAnnotationFollowed(),busy=ref(new Set())
 async function setFavorite(row,enabled){
  const kind=row.projectType||row.kind,id=row.projectId,key=`${kind}:${id}`
  if(!id||busy.value.has(key))return
  busy.value=new Set([...busy.value,key])
  const update=values=>{Object.assign(row,values);const raw=sessions.value.find(item=>item.key===key);if(raw)Object.assign(raw,values)}
  try{
   // 沿用账号原有 starred / following 记录；无需改写其他账号或迁移生产数据。
   if(kind==='annotation'){await annotationChatRequest(id,'following',{method:'put',data:{following:enabled}});update({following:enabled})}
   await chatRequest(kind==='discussion'?`discussions/${id}/preferences`:`sessions/${kind}/${id}/preferences`,{method:'put',data:{starred:enabled}})
   update({starred:enabled})
  }finally{busy.value=new Set([...busy.value].filter(item=>item!==key));await refresh()}
 }
 return {sessions,refresh,busy,setFavorite}
}
