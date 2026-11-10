import {ref} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api/index'
import {newNumberWindowId} from '@/utils/businessNumberLeases'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'

export function useProjectDelivery(module){
  const mailAlsoChat=ref(false),emergencyNotice=ref(false),chatAudience=ref([]),mailChatAudience=ref([])
  const requests=new Map()
  function prepareDelivery(emergency=false,chat=false){emergencyNotice.value=emergency;mailAlsoChat.value=chat;mailChatAudience.value=[...chatAudience.value]}
  async function sendConversation(projectId,emergency=false){
    if(!projectId){ElMessage.error('项目已保存，但未返回项目编号，暂不能发送会话');return false}
    const owner=localStorage.getItem('user_id'),key=`${owner}:${projectId}:${emergency}`
    if(!requests.has(key))requests.set(key,newNumberWindowId())
    try{
      await api.post(`/project-delivery/${module}/${projectId}/chat`,{request_key:requests.get(key),emergency_notice:emergency,audience:[...chatAudience.value]})
      requests.delete(key)
      ElMessage.success('项目已保存，会话已发送')
      return true
    }catch(error){ElMessage.error('项目已保存，会话发送失败：'+getLocalizedErrorMessage(error,'请重新打开项目后重试'));return false}
  }
  return {mailAlsoChat,emergencyNotice,chatAudience,mailChatAudience,prepareDelivery,sendConversation}
}
