<template>
  <div v-if="projectId" class="chat-session-quick-actions" @mousedown.stop @dblclick.stop>
    <el-button link :disabled="!session || busy" :aria-label="session?.pinned ? '取消置顶会话' : '置顶会话'" :title="session?.pinned ? '取消置顶会话' : '置顶会话'" :aria-pressed="!!session?.pinned" @click="save({pinned:!session.pinned})"><el-icon><Top /></el-icon></el-button>
    <el-button link :disabled="!session || busy" :aria-label="favorite ? '取消收藏会话' : '收藏会话'" :title="favorite ? '已收藏，点击取消收藏' : '加入收藏'" :aria-pressed="favorite" @click="toggleFavorite"><el-icon><StarFilled v-if="favorite" /><Star v-else /></el-icon></el-button>
    <el-button link :disabled="!session || busy" aria-label="标为已读" title="标为已读" @click="save({markRead:true})"><el-icon><Message /></el-icon></el-button>
  </div>
</template>
<script setup>
import {computed,ref} from 'vue'
import {Top,Star,StarFilled,Message} from '@element-plus/icons-vue'
import {ElMessage} from 'element-plus'
import {chatRequest} from '@/api/projectChat'
import {useChatFavorites} from '@/composables/useChatFavorites'
import {isSessionFavorite} from '@/utils/chatFavorites'
const props=defineProps({projectId:String,projectType:String})
const {sessions,refresh,setFavorite}=useChatFavorites()
const busy=ref(false)
const session=computed(()=>sessions.value.find(row=>row.projectId===props.projectId && (row.kind||row.projectType)===props.projectType))
const favorite=computed(()=>isSessionFavorite(session.value||{}))
async function toggleFavorite(){if(busy.value||!session.value)return;busy.value=true;try{await setFavorite(session.value,!favorite.value)}catch(error){ElMessage.error(error.detail||error.message||'更新收藏失败')}finally{busy.value=false}}
async function save(data){
  if(busy.value||!session.value)return
  const row=session.value,id=props.projectId,kind=props.projectType
  busy.value=true
  try{
    await chatRequest(kind==='discussion'?`discussions/${id}/preferences`:`sessions/${kind}/${id}/preferences`,{method:'put',data})
    if(data.pinned!==undefined)row.pinned=data.pinned
    if(data.starred!==undefined)row.starred=data.starred
    if(data.markRead){row.unread=0;row.mentionUnread=0}
    await refresh()
  }catch(error){ElMessage.error(error.detail||error.message||'更新会话状态失败')}
  finally{busy.value=false}
}
</script>
<style scoped>
.chat-session-quick-actions{display:flex;align-items:center;gap:2px;flex:none}
.chat-session-quick-actions .el-button{width:28px;height:28px;padding:4px;margin:0}
.chat-session-quick-actions .el-button[aria-pressed="true"]{color:var(--el-color-primary);background:var(--el-color-primary-light-9);border-radius:5px}
</style>
