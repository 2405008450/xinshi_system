<template>
  <span class="annotation-conversation-entry" :class="{'is-inline':inline}">
    <small :title="status?.error">{{ stateLabel }}</small>
    <el-button link type="primary" :loading="busy" :disabled="!status || (!status.error && !status.joined && !status.canJoin)" @click.stop="join">{{ actionLabel }}</el-button>
  </span>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { annotationChatRequest } from '@/api/projectChat'
import { useAnnotationConversationStatus } from '@/composables/useAnnotationConversationStatus'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
const props=defineProps({projectId:{type:String,required:true},inline:Boolean})
const emit=defineEmits(['joined'])
const {statuses,refresh}=useAnnotationConversationStatus()
const {sessions,refresh:refreshSessions}=useAnnotationFollowed()
const {state,revealSession,openChat}=useProjectChatDock()
const busy=ref(false)
const status=computed(()=>statuses[props.projectId])
const closed=computed(()=>state.closedSessionKeys.includes(`annotation:${props.projectId}`))
const stateLabel=computed(()=>!status.value?'加载状态…':status.value.error?'状态加载失败':status.value.joined?(closed.value?'已关闭':'已加入'):status.value.created?'已创建':'未创建')
const actionLabel=computed(()=>status.value?.error?'重试':status.value?.joined?(closed.value?'恢复会话':'打开会话'):status.value?.created?'加入会话':'创建会话')
watch(()=>props.projectId,refresh,{immediate:true})
async function join(){
  if(status.value?.error){refresh(props.projectId);return}
  busy.value=true
  try{
    if(!status.value.joined)await annotationChatRequest(props.projectId,'start',{method:'post'})
    await refreshSessions()
    let session=sessions.value.find(row=>row.key===`annotation:${props.projectId}`)
    if(!session){await annotationChatRequest(props.projectId,'following',{method:'put',data:{following:true}});await refreshSessions();session=sessions.value.find(row=>row.key===`annotation:${props.projectId}`)}
    const target={...session,key:`annotation:${props.projectId}`,projectId:props.projectId,projectType:'annotation'}
    revealSession(target)
    refresh(props.projectId)
    emit('joined',target)
    if(status.value.joined)openChat(target)
    ElMessage.success('已加入会话列表')
  }catch(e){ElMessage.error(e.detail || '创建／加入会话失败')}
  finally{busy.value=false}
}
</script>
<style scoped>.annotation-conversation-entry{display:inline-flex;flex-direction:column;align-items:flex-start;gap:3px;max-width:100%}.annotation-conversation-entry small{color:#64748b;font-size:11px;white-space:normal}.annotation-conversation-entry.is-inline{flex-direction:row;align-items:center;gap:12px;white-space:nowrap}.is-inline small{font-size:13px;white-space:nowrap}</style>
